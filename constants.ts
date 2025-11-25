/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
*/

import React from 'react';
import { Product, JournalArticle } from './types';

export const PRODUCTS: Product[] = [
  {
    id: 'p1',
    name: 'Aura Harmony',
    tagline: 'Listen naturally.',
    description: 'Audio that feels like the open air. Constructed with warm acoustic fabric and recycled sandstone composite.',
    longDescription: 'Experience sound as it was meant to be heard—unconfined and organic. The Aura Harmony headphones feature our proprietary open-air driver technology, encased in a breathable acoustic fabric that adapts to your temperature. The headband is crafted from a recycled sandstone composite, offering a unique, cool-to-the-touch texture that grounds you in the present moment.',
    price: 429,
    category: 'Audio',
    imageUrl: 'https://images.unsplash.com/photo-1505740420928-5e560c06d30e?auto=format&fit=crop&q=80&w=1000',
    gallery: [
      'https://images.unsplash.com/photo-1505740420928-5e560c06d30e?auto=format&fit=crop&q=80&w=1000',
      'https://images.unsplash.com/photo-1484704849700-f032a568e944?auto=format&fit=crop&q=80&w=1000',
      'https://images.unsplash.com/photo-1524678606372-565ae0f98944?auto=format&fit=crop&q=80&w=1000'
    ],
    features: ['Organic Noise Cancellation', '50h Battery', 'Natural Soundstage']
  },
  {
    id: 'p2',
    name: 'Aura Epoch',
    tagline: 'Moments, not minutes.',
    description: 'A timepiece designed for wellness. Ceramic casing with a strap made from sustainable vegan leather.',
    longDescription: 'Time is not a sequence of numbers, but a flow of moments. The Aura Epoch rethinks the smartwatch interface, using a calm E-Ink hybrid display that mimics paper. It tracks stress through skin temperature and heart rate variability, gently vibrating to remind you to breathe. The ceramic casing is hypoallergenic and smooth, polished by hand for 48 hours.',
    price: 349,
    category: 'Wearable',
    imageUrl: 'https://images.unsplash.com/photo-1523275335684-37898b6baf30?auto=format&fit=crop&q=80&w=1000',
    gallery: [
        'https://images.unsplash.com/photo-1523275335684-37898b6baf30?auto=format&fit=crop&q=80&w=1000',
        'https://images.unsplash.com/photo-1508685096489-7aacd43bd3b1?auto=format&fit=crop&q=80&w=1000'
    ],
    features: ['Stress Monitoring', 'E-Ink Hybrid Display', '7-Day Battery']
  },
  {
    id: 'p3',
    name: 'Aura Canvas',
    tagline: 'Capture the warmth.',
    description: 'A display that mimics the properties of paper. Soft on the eyes, vivid in color, and textured to the touch.',
    longDescription: 'Screens shouldn\'t feel like looking into a lightbulb. Aura Canvas uses a matte, nano-etched OLED panel that scatters ambient light, creating a display that looks and feels like high-quality magazine paper. Perfect for reading, sketching, or displaying art, it brings a tactile warmth to your digital life.',
    price: 1099,
    category: 'Mobile',
    imageUrl: 'https://images.unsplash.com/photo-1544816155-12df9643f363?auto=format&fit=crop&q=80&w=1000',
    gallery: [
        'https://images.unsplash.com/photo-1544816155-12df9643f363?auto=format&fit=crop&q=80&w=1000',
        'https://images.unsplash.com/photo-1585338107529-13afc5f02586?auto=format&fit=crop&q=80&w=1000'
    ],
    features: ['Paper-like OLED', 'Portrait Lens', 'Sandstone Texture']
  },
  {
    id: 'p4',
    name: 'Aura Essence',
    tagline: 'Return to nature.',
    description: 'An air purifier that doubles as a sculpture. Whisper quiet, diffusing subtle natural scents while cleaning your space.',
    longDescription: 'Clean air is the foundation of a clear mind. Aura Essence uses a moss-based bio-filter combined with HEPA technology to scrub pollutants from your home. It gently diffuses natural essential oils—cedar, bergamot, and rain—orchestrated to match the time of day.',
    price: 599,
    category: 'Home',
    imageUrl: 'https://images.pexels.com/photos/8092420/pexels-photo-8092420.jpeg?auto=compress&cs=tinysrgb&w=1260&h=750&dpr=1',
    gallery: [
        'https://images.pexels.com/photos/8092420/pexels-photo-8092420.jpeg?auto=compress&cs=tinysrgb&w=1260&h=750&dpr=1',
        'https://images.unsplash.com/photo-1513694203232-719a280e022f?auto=format&fit=crop&q=80&w=1000'
    ],
    features: ['Bio-HEPA Filter', 'Aromatherapy', 'Silent Night Mode']
  },
  {
    id: 'p5',
    name: 'Aura Beam',
    tagline: 'Light that breathes.',
    description: 'Smart circadian lighting that follows the sun. Casts a warm, candle-like glow in the evenings.',
    longDescription: 'Artificial light disrupts our natural rhythms. Aura Beam syncs with your local sunrise and sunset, providing cool, energizing light during the day and transitioning to a warm, amber glow free of blue light in the evening. Controls are touchless; a simple wave of the hand adjusts brightness.',
    price: 249,
    category: 'Home',
    imageUrl: 'https://images.unsplash.com/photo-1565814329452-e1efa11c5b89?auto=format&fit=crop&q=80&w=1000',
    gallery: [
        'https://images.unsplash.com/photo-1565814329452-e1efa11c5b89?auto=format&fit=crop&q=80&w=1000',
        'https://images.unsplash.com/photo-1540932296235-d84931b6370b?auto=format&fit=crop&q=80&w=1000'
    ],
    features: ['Circadian Rhythm Sync', 'Warm Dimming', 'Touchless Control']
  },
  {
    id: 'p6',
    name: 'Aura Scribe',
    tagline: 'Thought in motion.',
    description: 'A digital stylus with the friction of graphite. Charges wirelessly when magnetically attached to Aura Canvas.',
    longDescription: 'The connection between hand and brain is sacred. Aura Scribe features a custom elastomer tip that replicates the microscopic friction of graphite on paper. Weighted perfectly for balance, it disappears in your hand, leaving only your thoughts.',
    price: 129,
    category: 'Mobile',
    imageUrl: 'https://images.pexels.com/photos/2647376/pexels-photo-2647376.jpeg?auto=compress&cs=tinysrgb&w=1260&h=750&dpr=1',
    gallery: [
        'https://images.pexels.com/photos/2647376/pexels-photo-2647376.jpeg?auto=compress&cs=tinysrgb&w=1260&h=750&dpr=1',
        'https://images.unsplash.com/photo-1517260487576-8977430081d3?auto=format&fit=crop&q=80&w=1000'
    ],
    features: ['Zero Latency', 'Textured Tip', 'Wireless Charging']
  }
];

export const JOURNAL_ARTICLES: JournalArticle[] = [
    {
        id: 1,
        title: "The Psychology of Texture",
        date: "April 12, 2025",
        excerpt: "Why our fingertips crave natural surfaces in a world of glass and plastic.",
        image: "https://images.unsplash.com/photo-1617791160505-6f00504e3519?auto=format&fit=crop&q=80&w=1000",
        content: React.createElement(React.Fragment, null,
            React.createElement("p", { className: "mb-6 first-letter:text-5xl first-letter:font-serif first-letter:mr-3 first-letter:float-left text-[#5D5A53]" },
                "We live in a frictionless world. Our phones are smooth glass, our laptops polished aluminum, our countertops engineered quartz. There is no resistance, no grit, no grain. And yet, our biology craves it."
            ),
            React.createElement("p", { className: "mb-8 text-[#5D5A53]" },
                "The fingertips are among the most densely innervated parts of the human body. They are designed to read the story of an object—its age, its origin, its temperature. When we deny them this input, we experience a subtle form of sensory deprivation."
            ),
            React.createElement("blockquote", { className: "border-l-2 border-[#2C2A26] pl-6 italic text-xl text-[#2C2A26] my-10 font-serif" },
                "\"To touch is to know. To feel is to be grounded.\""
            ),
            React.createElement("p", { className: "mb-6 text-[#5D5A53]" },
                "At Aura, we design for the hand as much as for the eye. We choose materials that have a voice. Sandstone that warms under your palm. Fabric that has a weave you can trace. Wood that remembers the forest."
            )
        )
    },
    {
        id: 2,
        title: "Living with Less",
        date: "March 28, 2025",
        excerpt: "A conversation with architect Hiroshi Nakamura on the art of empty space.",
        image: "https://images.unsplash.com/photo-1494438639946-1ebd1d20bf85?auto=format&fit=crop&q=80&w=1000",
        content: React.createElement(React.Fragment, null,
            React.createElement("p", { className: "mb-6 text-[#5D5A53]" },
                "Emptiness is not nothing. In Japanese architecture, the concept of ",
                React.createElement("em", null, "Ma"),
                " refers to the space between things—the pause that gives shape to the whole."
            ),
            React.createElement("p", { className: "mb-8 text-[#5D5A53]" },
                "\"We tend to fill our lives with noise,\" Nakamura says, sipping tea in his studio overlooking the rain-slicked streets of Kyoto. \"We buy more devices to save time, but we end up with less time than ever. True luxury is the absence of intrusion.\""
            ),
            React.createElement("div", { className: "my-12 p-8 bg-[#EBE7DE] font-serif text-[#2C2A26] italic text-center" },
                React.createElement("p", null, "The room is empty"),
                React.createElement("p", null, "But full of light."),
                React.createElement("p", null, "The mind is quiet"),
                React.createElement("p", null, "But full of thought."),
                React.createElement("p", null, "This is the weight"),
                React.createElement("p", null, "Of living with less.")
            ),
            React.createElement("p", { className: "mb-6 text-[#5D5A53]" },
                "This philosophy drives every curve of our new collection. We asked ourselves: what can we remove? How much can we take away until only the essential remains?"
            )
        )
    },
    {
        id: 3,
        title: "Spring Moodboard",
        date: "March 15, 2025",
        excerpt: "Notes from the design studio: morning mist, wet stone, and pale linen.",
        image: "https://images.unsplash.com/photo-1516834474-48c0abc2a902?auto=format&fit=crop&q=80&w=1000",
        content: React.createElement(React.Fragment, null,
            React.createElement("p", { className: "mb-6 text-[#5D5A53]" },
                "Spring in the studio is a time of awakening. The light shifts from the harsh, low angles of winter to a softer, diffused glow. We find ourselves drawn to paler tones—the grey of wet pavement, the cream of unbleached linen, the dusty green of sage."
            ),
            React.createElement("p", { className: "mb-8 text-[#5D5A53]" },
                "Our moodboard this month is a study in softness. It is about the transition state—neither cold nor hot, neither dark nor bright. It is the dawn of the year."
            ),
             React.createElement("div", { className: "my-12 p-8 bg-[#2C2A26] text-[#F5F2EB] font-serif italic text-center" },
                React.createElement("p", null, "Green sprout pushing through"),
                React.createElement("p", null, "Grey stone cold against the skin"),
                React.createElement("p", null, "The sun warms the air.")
            )
        )
    }
];

export const BRAND_NAME = 'Aura';
export const PRIMARY_COLOR = 'stone-900'; 
export const ACCENT_COLOR = 'stone-500';