import path from 'node:path';
import { defineConfig } from 'prisma/config';

// Prisma 7 keeps the connection URL here rather than in the schema.
export default defineConfig({
  schema: path.join('prisma', 'schema.prisma'),
  migrations: {
    path: path.join('prisma', 'migrations'),
  },
  datasource: {
    url: process.env.DATABASE_URL ?? 'file:./prisma/dev.db',
  },
});
