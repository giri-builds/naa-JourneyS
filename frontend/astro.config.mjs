import { defineConfig } from 'astro/config';
import react from '@astrojs/react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  site: 'https://YOUR_USERNAME.github.io',
  base: '/naa-JourneyS/',
  integrations: [react()],
  vite: {
    plugins: [tailwindcss()]
  }
});
