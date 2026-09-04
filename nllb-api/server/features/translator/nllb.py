from collections.abc import Iterator
from pathlib import Path
from typing import Self

from ctranslate2 import Translator as CTranslator
from tokenizers import Tokenizer

from server.features.translator.protocol import TranslatorProtocol
from server.features.translator.stub import TranslatorStub
from server.logging_config import get_logger
from server.typedefs import Language
from server.utils import huggingface_download

logger = get_logger(__name__)


class Translator(TranslatorProtocol):
    """
    Summary
    -------
    a class for the NLLB translator

    Methods
    -------
    translate_generator(text: str, source_language: Language, target_language: Language) -> Iterator[str]
        translate the input from the source language to the target language tokens

    translate(text: str, source_language: Language, target_language: Language) -> str
        translate the input from the source language to the target language

    translate_stream(text: str, source_language: Language, target_language: Language) -> Iterator[str]
        streams the translation input from the source language to the target language

    unload_model(to_cpu: bool) -> bool
        unload the model from the current device

    load_model(keep_cache: bool) -> bool
        load the model back to the initial device

    count_tokens(text: str) -> int
        count the number of tokens in the input text
    """

    __slots__ = ("tokeniser", "translator", "use_cuda")

    def __init__(self, translator: CTranslator, tokeniser: Tokenizer, *, use_cuda: bool) -> None:
        self.tokeniser = tokeniser
        self.translator = translator
        self.use_cuda = use_cuda

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_) -> None:
        del self.tokeniser
        del self.translator

    def unload_model(self, *, to_cpu: bool) -> bool:
        """
        Summary
        -------
        unload the model from the current device

        Parameters
        ----------
        to_cpu (bool)
            whether to unload the model to CPU

        Returns
        -------
        success (bool)
            whether the model unload was executed
        """
        if not self.translator.model_is_loaded:
            return False

        self.translator.unload_model(to_cpu=self.use_cuda and to_cpu)
        return True

    def load_model(self, *, keep_cache: bool) -> bool:
        """
        Summary
        -------
        load the model back to the initial device

        Parameters
        ----------
        keep_cache (bool)
            whether to keep the model cache in RAM

        Returns
        -------
        success (bool)
            whether the model load was executed
        """
        if self.translator.model_is_loaded:
            return False

        self.translator.load_model(keep_cache=self.use_cuda and keep_cache)
        return True

    def count_tokens(self, text: str) -> int:
        """
        Summary
        -------
        count the number of tokens in the input text

        Parameters
        ----------
        text (str)
            the input text

        Returns
        -------
        token_count (int)
            the number of tokens that will be sent to the translator
        """
        return len(self.tokeniser.encode(text)) + 1

    def translate_generator(
        self, text: str, source_language: Language, target_language: Language, min_length_percentage: float = 0.8
    ) -> Iterator[int]:
        """
        Summary
        -------
        translate the input from the source language to the target language tokens

        Parameters
        ----------
        text (str)
            the input to translate

        source_language (Languages)
            the source language

        target_language (Languages)
            the target languages

        min_length_percentage (float)
            minimum decoding length as percentage of input tokens (0.0-1.0).
            Defaults to 0.8 (80%). Used to prevent early stopping in NLLB models.
            See: https://huggingface.co/facebook/nllb-200-distilled-600M/discussions/6

        Returns
        -------
        token_indices (Iterator[int]) : the translated tokens indices
        """
        input_length = len(text)
        logger.debug(
            "Starting translation generation",
            input_length=input_length,
            source_language=source_language,
            target_language=target_language,
            min_length_percentage=min_length_percentage,
            text_preview=text[:100] + "..." if len(text) > 100 else text,
        )
        
        target_prefix = (target_language,)
        # Calculate minimum decoding length based on input length to prevent early stopping
        # NLLB models can stop early - see: https://huggingface.co/facebook/nllb-200-distilled-600M/discussions/6
        # Use the specified percentage of input tokens as minimum decoding length
        input_tokens = len(self.tokeniser.encode(text).tokens)
        min_decoding_length = max(1, int(input_tokens * min_length_percentage))
        
        results = self.translator.generate_tokens(
            (source_language, *self.tokeniser.encode(text).tokens),
            target_prefix,
            max_decoding_length=4096,
            min_decoding_length=min_decoding_length,
            sampling_temperature=0,
            no_repeat_ngram_size=3,
            suppress_sequences=(target_prefix,),
        )

        # Include all tokens, including the last one
        # is_last indicates the final token of the generation, which we need to include
        # Filtering it out was causing truncation in single translations
        token_count = 0
        is_last_count = 0
        last_is_last = False
        
        def token_generator():
            nonlocal token_count, is_last_count, last_is_last
            for result in results:
                token_count += 1
                if result.is_last:
                    is_last_count += 1
                    last_is_last = True
                    logger.debug(
                        "Encountered is_last=True token",
                        token_id=result.token_id,
                        step=result.step,
                        token_count=token_count,
                    )
                yield result.token_id
            
            logger.debug(
                "Translation generation complete",
                total_tokens=token_count,
                is_last_tokens=is_last_count,
                last_was_is_last=last_is_last,
            )
        
        return token_generator()

    def translate_batch(
        self,
        texts: list[str],
        source_languages: list[Language],
        target_languages: list[Language],
        min_length_percentages: list[float] | None = None,
    ) -> list[str]:
        """
        Summary
        -------
        translate multiple inputs from source languages to target languages in batch

        Parameters
        ----------
        texts (list[str])
            list of input texts to translate

        source_languages (list[Language])
            list of source languages corresponding to each text

        target_languages (list[Language])
            list of target languages corresponding to each text

        min_length_percentages (list[float] | None)
            minimum decoding length as percentage of input tokens (0.0-1.0) for each text.
            If None, defaults to 0.8 (80%) for all items. Uses the minimum token count
            across all items to compute a safe min_decoding_length for batch processing.
            Used to prevent early stopping in NLLB models.
            See: https://huggingface.co/facebook/nllb-200-distilled-600M/discussions/6

        Returns
        -------
        translated_texts (list[str])
            list of translated texts in the same order as input
        """
        if not texts:
            return []

        # Default to 0.8 for all items if not provided
        if min_length_percentages is None:
            min_length_percentages = [0.8] * len(texts)
        
        # Ensure we have the same number of percentages as texts
        if len(min_length_percentages) != len(texts):
            raise ValueError(
                f"Number of min_length_percentages ({len(min_length_percentages)}) "
                f"must match number of texts ({len(texts)})"
            )

        logger.debug(
            "Starting batch translation",
            batch_size=len(texts),
            text_lengths=[len(t) for t in texts],
            min_length_percentages=min_length_percentages,
        )

        # Encode all texts and calculate token counts
        encoded_texts = [self.tokeniser.encode(text) for text in texts]
        token_counts = [len(encoded.tokens) for encoded in encoded_texts]
        
        # Calculate min_decoding_length based on minimum token count to avoid forcing
        # short texts to generate too many tokens, while still preventing early stopping
        min_token_count = min(token_counts) if token_counts else 1
        # Use the minimum percentage to be conservative
        min_percentage = min(min_length_percentages)
        min_decoding_length = max(1, int(min_token_count * min_percentage))

        # Prepare batch inputs with language prefixes
        # Format: list of lists of strings (tokens)
        # CTranslate2 expects list[list[str]] where each inner list is [source_lang, token1, token2, ...]
        # Match the format used in single translation: (source_language, *tokens)
        batch_inputs = []
        for source_lang, encoded in zip(source_languages, encoded_texts):
            # Create a list with source language followed by tokens (same as single translation)
            batch_input = [source_lang] + encoded.tokens
            batch_inputs.append(batch_input)
        
        # target_prefix should be list of lists (one per input)
        # Match the format used in single translation: (target_language,)
        target_prefixes = [[target_lang] for target_lang in target_languages]

        # Use native batch translation for GPU efficiency
        # suppress_sequences should match target_prefix format: list[list[str]]
        batch_results = self.translator.translate_batch(
            batch_inputs,
            target_prefix=target_prefixes,
            max_decoding_length=4096,
            min_decoding_length=min_decoding_length,
            sampling_temperature=0,
            no_repeat_ngram_size=3,
            suppress_sequences=target_prefixes,  # Suppress target language prefix sequences
        )

        # Decode all results
        # hypotheses contains token IDs - check if they're strings or integers
        decoded_texts = []
        for idx, result in enumerate(batch_results):
            try:
                if not hasattr(result, "hypotheses"):
                    logger.error(
                        "Result missing hypotheses attribute",
                        item_index=idx,
                        result_type=type(result).__name__,
                        result_attrs=dir(result),
                    )
                    raise ValueError(f"Result missing hypotheses attribute for batch item {idx}")
                
                if not result.hypotheses or len(result.hypotheses) == 0:
                    logger.error(
                        "Empty hypotheses in batch result",
                        item_index=idx,
                        result_type=type(result).__name__,
                        has_hypotheses=hasattr(result, "hypotheses"),
                    )
                    raise ValueError(f"Empty hypotheses for batch item {idx}")
                
                # Get the first hypothesis (best translation)
                hypothesis = result.hypotheses[0]
                
                if not hypothesis or len(hypothesis) == 0:
                    logger.error(
                        "Empty hypothesis in batch result",
                        item_index=idx,
                        hypotheses_count=len(result.hypotheses),
                    )
                    raise ValueError(f"Empty hypothesis for batch item {idx}")
                
                # CTranslate2 translate_batch returns hypotheses as list[list[str]]
                # The hypothesis includes the target language prefix (e.g., 'spa_Latn') at the start
                # followed by token strings (not token IDs) - these are already decoded tokens
                target_lang = target_languages[idx]
                
                # Filter out the target language prefix and join the remaining token strings
                # Token strings from CTranslate2 are already decoded, we just need to join them
                token_strings = []
                for token in hypothesis:
                    # Skip target language prefix
                    if token == target_lang:
                        continue
                    token_strings.append(token)
                
                if not token_strings:
                    logger.error(
                        "No tokens found in hypothesis after filtering target language prefix",
                        item_index=idx,
                        hypothesis=hypothesis,
                        target_lang=target_lang,
                    )
                    raise ValueError(f"No tokens found in hypothesis for batch item {idx}")
                
                # Join token strings - CTranslate2 returns token strings, not IDs
                # The token strings may contain special characters like \u2581 (word boundary)
                # which need to be handled properly
                decoded_text = "".join(token_strings).replace("\u2581", " ").strip()
                decoded_texts.append(decoded_text)
            except (ValueError, IndexError, TypeError, AttributeError) as e:
                logger.error(
                    "Error decoding batch result",
                    item_index=idx,
                    error=str(e),
                    error_type=type(e).__name__,
                    has_hypotheses=hasattr(result, "hypotheses"),
                    hypotheses_length=len(result.hypotheses) if hasattr(result, "hypotheses") and result.hypotheses else 0,
                    result_type=type(result).__name__,
                    result_attrs=dir(result) if hasattr(result, "__dict__") else "no __dict__",
                )
                raise

        logger.debug(
            "Batch translation complete",
            total_items=len(decoded_texts),
            min_decoding_length=min_decoding_length,
            total_output_length=sum(len(t) for t in decoded_texts),
        )
        
        return decoded_texts

    def translate(
        self, text: str, source_language: Language, target_language: Language, min_length_percentage: float = 0.8
    ) -> str:
        """
        Summary
        -------
        translate the input from the source language to the target language

        Parameters
        ----------
        text (str)
            the input to translate

        source_language (Languages)
            the source language

        target_language (Languages)
            the target language

        min_length_percentage (float)
            minimum decoding length as percentage of input tokens (0.0-1.0).
            Defaults to 0.8 (80%). Used to prevent early stopping in NLLB models.
            See: https://huggingface.co/facebook/nllb-200-distilled-600M/discussions/6

        Returns
        -------
        translated_text (str)
            the translated text
        """
        token_ids = list(self.translate_generator(text, source_language, target_language, min_length_percentage))
        decoded_text = self.tokeniser.decode(token_ids, skip_special_tokens=True)
        
        logger.debug(
            "Translation complete",
            input_length=len(text),
            token_count=len(token_ids),
            output_length=len(decoded_text),
            output_preview=decoded_text[:100] + "..." if len(decoded_text) > 100 else decoded_text,
        )
        
        return decoded_text

    def translate_stream(
        self, text: str, source_language: Language, target_language: Language, min_length_percentage: float = 0.8
    ) -> Iterator[str]:
        """
        Summary
        -------
        streams the translation input from the source language to the target language

        Parameters
        ----------
        text (str)
            the input to translate

        source_language (Languages)
            the source language

        target_language (Languages)
            the target language

        min_length_percentage (float)
            minimum decoding length as percentage of input tokens (0.0-1.0).
            Defaults to 0.8 (80%). Used to prevent early stopping in NLLB models.
            See: https://huggingface.co/facebook/nllb-200-distilled-600M/discussions/6

        Returns
        -------
        translated_text (Iterator[str])
            the translated text
        """

        return (
            self.tokeniser.decode((token,))
            for token in self.translate_generator(text, source_language, target_language, min_length_percentage)
        )


def get_translator(
    repository: str,
    *,
    translator_threads: int,
    stub: bool,
    testing: bool,
    use_cuda: bool,
) -> TranslatorProtocol:
    """
    Summary
    -------
    get the translator object

    Parameters
    ----------
    repository (str)
        the repository to download the model from

    translator_threads (int)
        the number of threads to use for the translator

    stub (bool)
        whether to return a stub object

    testing (bool)
        whether the application is running in testing mode

    use_cuda (bool)
        whether to use CUDA for inference

    Returns
    -------
    translator (TranslatorProtocol)
        the translator
    """
    if stub:
        return TranslatorStub()

    model_path = huggingface_download(repository)
    tokeniser = Tokenizer.from_file(str(Path(model_path) / "tokenizer.json"))
    
    # Check if CUDA is actually available
    device = "cuda" if use_cuda else "cpu"
    if use_cuda:
        try:
            # Try to create a translator with CUDA to check availability
            # This will fail if CUDA libraries aren't available
            test_translator = CTranslator(
                model_path,
                "cuda",
                compute_type="default" if testing else "auto",
                inter_threads=translator_threads,
            )
            # If successful, use CUDA
            translator = test_translator
            logger.info("CUDA device initialized successfully")
        except (RuntimeError, OSError) as e:
            # CUDA not available, fall back to CPU
            logger.warning("CUDA requested but not available, falling back to CPU", error=str(e))
            device = "cpu"
            translator = CTranslator(
                model_path,
                "cpu",
                compute_type="default" if testing else "auto",
                inter_threads=translator_threads,
            )
    else:
        translator = CTranslator(
            model_path,
            "cpu",
            compute_type="default" if testing else "auto",
            inter_threads=translator_threads,
        )

    return Translator(translator, tokeniser, use_cuda=(device == "cuda"))
