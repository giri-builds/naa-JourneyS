import { defineConfig } from 'astro/config';
import react from '@astrojs/react';
import tailwindcss from '@tailwindcss/vite';
import remarkBreaks from 'remark-breaks';

export default defineConfig({
  site: 'https://YOUR_USERNAME.github.io',
  base: '/naa-JourneyS/',
  integrations: [react()],
  markdown: {
    remarkPlugins: [remarkBreaks],
  },
  vite: {
    plugins: [tailwindcss()]
  }
});
