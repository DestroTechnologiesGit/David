---
license: apache-2.0
language:
- multilingual
- en
- ru
- es
- fr
- de
- it
- pt
- pl
- nl
- vi
- tr
- sv
- id
- ro
- cs
- zh
- hu
- ja
- th
- fi
- fa
- uk
- da
- el
- 'no'
- bg
- sk
- ko
- ar
- lt
- ca
- sl
- he
- et
- lv
- hi
- sq
- ms
- az
- sr
- ta
- hr
- kk
- is
- ml
- mr
- te
- af
- gl
- fil
- be
- mk
- eu
- bn
- ka
- mn
- bs
- uz
- ur
- sw
- yue
- ne
- kn
- kaa
- gu
- si
- cy
- eo
- la
- hy
- ky
- tg
- ga
- mt
- my
- km
- tt
- so
- ku
- ps
- pa
- rw
- lo
- ha
- dv
- fy
- lb
- ckb
- mg
- gd
- am
- ug
- ht
- grc
- hmn
- sd
- jv
- mi
- tk
- ceb
- yi
- ba
- fo
- or
- xh
- su
- kl
- ny
- sm
- sn
- co
- zu
- ig
- yo
- pap
- st
- haw
- as
- oc
- cv
- lus
- tet
- gsw
- sah
- br
- rm
- sa
- bo
- om
- se
- ce
- cnh
- ilo
- hil
- udm
- os
- lg
- ti
- vec
- ts
- tyv
- kbd
- ee
- iba
- av
- kha
- to
- tn
- nso
- fj
- zza
- ak
- ada
- otq
- dz
- bua
- cfm
- ln
- chm
- gn
- krc
- wa
- hif
- yua
- srn
- war
- rom
- bik
- pam
- sg
- lu
- ady
- kbp
- syr
- ltg
- myv
- iso
- kac
- bho
- ay
- kum
- qu
- za
- pag
- ngu
- ve
- pck
- zap
- tyz
- hui
- bbc
- tzo
- tiv
- ksd
- gom
- min
- ang
- nhe
- bgp
- nzi
- nnb
- nv
- zxx
- bci
- kv
- new
- mps
- alt
- meu
- bew
- fon
- iu
- abt
- mgh
- mnw
- tvl
- dov
- tlh
- ho
- kw
- mrj
- meo
- crh
- mbt
- emp
- ace
- ium
- mam
- gym
- mai
- crs
- pon
- ubu
- fip
- quc
- gv
- kj
- btx
- ape
- chk
- rcf
- shn
- tzh
- mdf
- ppk
- ss
- gag
- cab
- kri
- seh
- ibb
- tbz
- bru
- enq
- ach
- cuk
- kmb
- wo
- kek
- qub
- tab
- bts
- kos
- rwo
- cak
- tuc
- bum
- cjk
- gil
- stq
- tsg
- quh
- mak
- arn
- ban
- jiv
- sja
- yap
- tcy
- toj
- twu
- xal
- amu
- rmc
- hus
- nia
- kjh
- bm
- guh
- mas
- acf
- dtp
- ksw
- bzj
- din
- zne
- mad
- msi
- mag
- mkn
- kg
- lhu
- ch
- qvi
- mh
- djk
- sus
- mfe
- srm
- dyu
- ctu
- gui
- pau
- inb
- bi
- mni
- guc
- jam
- wal
- jac
- bas
- gor
- skr
- nyu
- noa
- sda
- gub
- nog
- cni
- teo
- tdx
- sxn
- rki
- nr
- frp
- alz
- taj
- lrc
- cce
- rn
- jvn
- hvn
- nij
- dwr
- izz
- msm
- bus
- ktu
- chr
- maz
- tzj
- suz
- knj
- bim
- gvl
- bqc
- tca
- pis
- prk
- laj
- mel
- qxr
- niq
- ahk
- shp
- hne
- spp
- koi
- krj
- quf
- luz
- agr
- tsc
- mqy
- gof
- gbm
- miq
- dje
- awa
- bjj
- qvz
- sjp
- tll
- raj
- kjg
- bgz
- quy
- cbk
- akb
- oj
- ify
- mey
- ks
- cac
- brx
- qup
- syl
- jax
- ff
- ber
- tks
- trp
- mrw
- adh
- smt
- srr
- ffm
- qvc
- mtr
- ann
- kaa
- aa
- noe
- nut
- gyn
- kwi
- xmm
- msb
library_name: transformers
tags:
- text2text-generation
- text-generation-inference
datasets:
- allenai/MADLAD-400
pipeline_tag: translation
metrics:
- bleu
---

# Model Card for MADLAD-400-3B-CT2-int8

#  Table of Contents

0. [TL;DR](#TL;DR)
1. [Model Details](#model-details)
2. [Usage](#usage)
3. [Uses](#uses)
4. [Bias, Risks, and Limitations](#bias-risks-and-limitations)
5. [Training Details](#training-details)
6. [Evaluation](#evaluation)
7. [Environmental Impact](#environmental-impact)
8. [Citation](#citation)

# TL;DR

MADLAD-400-3B-MT is a multilingual machine translation model based on the T5 architecture that was
trained on 1 trillion tokens covering over 450 languages using publicly available data.
It is competitive with models that are significantly larger.

**Disclaimer**: [Heng-Shiou Sheu](https://huggingface.co/Heng666), who was not involved in this research, converted 
the original models to CTranslate2 optimized model and wrote the contents of this model card based on [google/madlad400-3b-mt](https://huggingface.co/google/madlad400-3b-mt).

# Model Details

## Model Description

- **Model type:** Language model
- **Language(s) (NLP):** Multilingual (400+ languages)
- **License:** Apache 2.0
- **Related Models:** [All MADLAD-400 Checkpoints](https://huggingface.co/models?search=madlad)
- **Original Checkpoints:** [All Original MADLAD-400 Checkpoints](https://github.com/google-research/google-research/tree/master/madlad_400)
- **Resources for more information:**
  - [Research paper](https://arxiv.org/abs/2309.04662)
  - [GitHub Repo](https://github.com/google-research/t5x)
  - [Hugging Face MADLAD-400 Docs (Similar to T5) ](https://huggingface.co/docs/transformers/model_doc/MADLAD-400) - [Pending PR](https://github.com/huggingface/transformers/pull/27471)

# Usage

Find below some example scripts on how to use the model:

## Running the model on a CPU or GPU

First, install the CTranslate2 packages that are required:

`pip install ctranslate2 sentencepiece`

```python
import ctranslate2
from sentencepiece import SentencePieceProcessor
from huggingface_hub import snapshot_download

model_name = "Heng666/madlad400-3b-ct2-int8"
model_path = snapshot_download(model_name)

tokenizer = SentencePieceProcessor()
tokenizer.load(f"{model_path}/sentencepiece.model")
translator = ctranslate2.Translator(model_path)

input_text = "I love pizza!"
input_tokens = tokenizer.encode(f"<2{target_language}> {input_text}", out_type=str)
results = translator.translate_batch(
    [input_tokens],
    batch_type="tokens",
    max_batch_size=1024,
    beam_size=1,
    no_repeat_ngram_size=1,
    repetition_penalty=2,
)
translated_sentence = tokenizer.decode(results[0].hypotheses[0])
print(translated_sentence)
# Eu adoro pizza!
```


# Uses

## Direct Use and Downstream Use

> Primary intended uses: Machine Translation and multilingual NLP tasks on over 400 languages.
> Primary intended users: Research community.

## Out-of-Scope Use

> These models are trained on general domain data and are therefore not meant to
> work on domain-specific models out-of-the box. Moreover, these research models have not been assessed
> for production usecases.

# Bias, Risks, and Limitations

> We note that we evaluate on only 204 of the languages supported by these models and on machine translation
> and few-shot machine translation tasks. Users must consider use of this model carefully for their own
> usecase.

## Ethical considerations and risks

> We trained these models with MADLAD-400 and publicly available data to create baseline models that
> support NLP for over 400 languages, with a focus on languages underrepresented in large-scale corpora.
> Given that these models were trained with web-crawled datasets that may contain sensitive, offensive or
> otherwise low-quality content despite extensive preprocessing, it is still possible that these issues to the
> underlying training data may cause differences in model performance and toxic (or otherwise problematic)
> output for certain domains. Moreover, large models are dual use technologies that have specific risks
> associated with their use and development. We point the reader to surveys such as those written by
> Weidinger et al. or Bommasani et al. for a more detailed discussion of these risks, and to Liebling
> et al. for a thorough discussion of the risks of machine translation systems.

## Known Limitations

More information needed

## Sensitive Use:

More information needed

# Training Details

> We train models of various sizes: a 3B, 32-layer parameter model,
> a 7.2B 48-layer parameter model and a 10.7B 32-layer parameter model.
> We share all parameters of the model across language pairs,
> and use a Sentence Piece Model with 256k tokens shared on both the encoder and decoder
> side. Each input sentence has a <2xx> token prepended to the source sentence to indicate the target
> language.

See the [research paper](https://arxiv.org/pdf/2309.04662.pdf) for further details.

## Training Data

> For both the machine translation and language model, MADLAD-400 is used. For the machine translation
> model, a combination of parallel datasources covering 157 languages is also used. Further details are
> described in the [paper](https://arxiv.org/pdf/2309.04662.pdf).

## Training Procedure

See the [research paper](https://arxiv.org/pdf/2309.04662.pdf) for further details.

# Evaluation

## Testing Data, Factors & Metrics

> For evaluation, we used WMT, NTREX, Flores-200 and Gatones datasets as described in Section 4.3 in the [paper](https://arxiv.org/pdf/2309.04662.pdf).

> The translation quality of this model varies based on language, as seen in the paper, and likely varies on
> domain, though we have not assessed this.

## Results

![image/png](https://cdn-uploads.huggingface.co/production/uploads/64b7f632037d6452a321fa15/EzsMD1AwCuFH0S0DeD-n8.png)

![image/png](https://cdn-uploads.huggingface.co/production/uploads/64b7f632037d6452a321fa15/CJ5zCUVy7vTU76Lc8NZcK.png)

![image/png](https://cdn-uploads.huggingface.co/production/uploads/64b7f632037d6452a321fa15/NK0S-yVeWuhKoidpLYh3m.png)

See the [research paper](https://arxiv.org/pdf/2309.04662.pdf) for further details.

# Environmental Impact

More information needed

# Citation

**BibTeX:**

```bibtex
@misc{kudugunta2023madlad400,
      title={MADLAD-400: A Multilingual And Document-Level Large Audited Dataset}, 
      author={Sneha Kudugunta and Isaac Caswell and Biao Zhang and Xavier Garcia and Christopher A. Choquette-Choo and Katherine Lee and Derrick Xin and Aditya Kusupati and Romi Stella and Ankur Bapna and Orhan Firat},
      year={2023},
      eprint={2309.04662},
      archivePrefix={arXiv},
      primaryClass={cs.CL}
}
```