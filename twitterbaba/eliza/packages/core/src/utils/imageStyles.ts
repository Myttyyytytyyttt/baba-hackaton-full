export interface ImageStyle {
  name: string;
  description: string;
  prompt: string;
}

export const IMAGE_STYLES: Record<string, ImageStyle> = {
  ANIME_JAPAN: {
    name: "Japan Anime Style",
    description: "Bold lines, big expressive eyes, soft lighting, and dreamy vibes like manga or Studio Ghibli",
    prompt: "Japan anime style, bold lines, big expressive eyes, soft lighting, dreamy vibes"
  },
  CYBERPUNK: {
    name: "Cyberpunk",
    description: "Neon-lit, Blade Runner, future-city vibe with dark tones, purples, blues, and electric glow",
    prompt: "Cyberpunk style with glowing neon lights, dark tones, purples, blues, electric glow, futuristic"
  },
  GHIBLI: {
    name: "Ghibli Style",
    description: "Painterly anime look with soft watercolor textures and lush environments in Studio Ghibli style",
    prompt: "Ghibli style, painterly anime look, soft watercolor textures, lush natural environments, emotionally expressive characters with large eyes, subtle magical realism, nostalgic atmosphere, warm lighting, gentle brushwork"
  },
  PIXAR: {
    name: "Pixar 3D Style",
    description: "Charming 3D animated style with clean, stylized character designs and cinematic warm lighting",
    prompt: "Pixar 3D style, charming animated style, clean stylized character designs with expressive yet subtle facial animation, cinematic warm lighting, beautifully composed shots, high-quality polished textures, and a heartwarming tone"
  },
  FLEISCHER: {
    name: "Fleischer Studios Style",
    description: "1930s rubber-hose cartoon style with surreal, bouncy physics and jazz-age character design",
    prompt: "1930s rubber-hose cartoon style, surreal, bouncy physics, jazz-age character design, pie-cut eyes, looping animation feel, hand-inked outlines, vintage backgrounds with film grain texture"
  },
  RICK_AND_MORTY: {
    name: "Rick and Morty Style",
    description: "Surreal sci-fi cartoon style with wobbly outlines and exaggerated facial expressions",
    prompt: "Rick and Morty style, surreal sci-fi cartoon style, flat 2D with wobbly outlines, exaggerated facial expressions, grotesque humor, absurd proportions, chaotic alien worlds, dimensional portals, and a muted palette lit with electric pops of color"
  },
  PIXEL_ART: {
    name: "Retro Pixel Game Style",
    description: "Authentic low-resolution pixel art in the style of retro 8-bit or 16-bit video games",
    prompt: "Authentic low-resolution pixel art, retro 8-bit or 16-bit video game style, clean blocky pixel style with no pixel borders, limited color palette with visible dithering and sharp contrast, classic NES or SNES games aesthetic, crisp sprite-like rendering"
  },
  MARBLE: {
    name: "Marble Style",
    description: "Hyper-realistic marble sculpture with polished finish and dramatic lighting",
    prompt: "Hyper-realistic marble sculpture, all-white polished marble with glossy finish, reflecting soft ambient light, deep shadows and highlights for sculptural depth, smooth and finely detailed texture resembling polished Carrara marble, high-relief marble carving, classical Greco-Roman aesthetic, dramatic lighting to define contours"
  },
  LEGO: {
    name: "Lego Style",
    description: "Made entirely of plastic bricks with blocky shapes and visible stud textures",
    prompt: "Lego style, made entirely of plastic bricks, blocky shapes, visible stud textures, modular construction, bright primary colors, characters with iconic Lego faces and claw hands, 3D toy-like rendering"
  },
  DOLLAR_BILL: {
    name: "Dollar Bill Style",
    description: "Vintage dollar bill with intricate engraved linework and monochrome green tones",
    prompt: "Vintage dollar bill style, intricate engraved linework, monochrome green tones, ornate borders, classical portrait framing, fine hatch shading, formal currency-like composition with official emblems or seals"
  },
  CLAYMATION: {
    name: "Claymation / Stop-Motion Style",
    description: "Handmade clay textures with visible fingerprints and a stop-motion aesthetic",
    prompt: "Claymation style, handmade clay textures, visible fingerprints and smudges, slightly uneven proportions, stop-motion aesthetic, soft lighting, expressive sculpted faces"
  },
  LOW_POLY: {
    name: "Low Poly 3D Style",
    description: "Simplified geometry with hard angular edges and flat color shading",
    prompt: "Low poly 3D style, simplified geometry, hard angular edges, flat color shading, minimalist lighting, retro 3D look"
  },
  VAPORWAVE: {
    name: "Vaporwave Style",
    description: "Neon pinks and purples with chrome textures and 1980s retrofuturistic aesthetic",
    prompt: "Vaporwave style, neon pinks and purples, chrome textures, digital sunset gradients, 1980s retrofuturistic aesthetic, grid backgrounds, nostalgic surrealism"
  },
  UKIYO_E: {
    name: "Ukiyo-e Style",
    description: "Traditional Japanese woodblock print aesthetic with fine ink lines and flat colors",
    prompt: "Ukiyo-e style, traditional Japanese woodblock print aesthetic, fine ink lines, flat colors, wave or cloud motifs, historical composition, stylized pattern backgrounds"
  },
  SURREALISM: {
    name: "Surrealism (Dalí-Inspired) Style",
    description: "Dreamlike distortion with melting shapes and floating objects",
    prompt: "Surrealism style, dreamlike distortion, melting shapes, floating objects, unexpected combinations, Dalí-inspired forms, symbolic and irrational visuals"
  },
  STEAMPUNK: {
    name: "Steampunk Style",
    description: "Victorian sci-fi aesthetic with brass gears and steam-powered machinery",
    prompt: "Steampunk style, Victorian sci-fi aesthetic, brass gears, steam-powered machinery, leather and rivets, mechanical enhancements, sepia tones"
  },
  LINE_ART: {
    name: "Line Art / Ink Drawing Style",
    description: "Clean black ink outlines with minimal or no color and cross-hatching for shading",
    prompt: "Line art style, clean black ink outlines, minimal or no color, cross-hatching for shading, sketchbook or pen-and-ink aesthetic"
  },
  DOODLE: {
    name: "Doodle Art Style",
    description: "Playful random sketches with cartoonish exaggeration and a hand-drawn aesthetic",
    prompt: "Doodle art style, playful random sketches, cartoonish exaggeration, hand-drawn aesthetic, overlapping line work, spontaneous composition"
  }
}; 