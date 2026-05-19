import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

const journey = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/journey' }),
  schema: z.object({
    title: z.string(),
    order: z.number(),
    dateRange: z.string(),
    yearRange: z.string(),
    place: z.string(),
    category: z.string(),
    tags: z.array(z.string()).optional(),
    coverImage: z.string().optional(),
    summary: z.string(),
  }),
});

export const collections = { journey };
