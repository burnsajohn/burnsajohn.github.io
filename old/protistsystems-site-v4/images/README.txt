IMAGES NEEDED
=============

hero-radiolarian.jpg   The splash image. Wide crop, ideally 2400 x 1400 or
                       larger. The type sits over the lower-left, so choose a
                       crop where that area is dark or quiet. A scrim darkens
                       it further, so a busy image still works.

Project thumbnails, referenced by projects/*.qmd. Square or 4:3, about 900 px:

  oophila.jpg          Symbiosis in the salamander egg
  radiolarian.jpg      Radiolarian genomics
  acantharian.jpg      Acantharian biomineralization
  genomes.jpg          Predicting cell biology from genomes
  sediment.jpg         Novel lineages from marine sediment

favicon.png            32 x 32 or 64 x 64.

The site renders fine before these exist. The hero falls back to a dark green
gradient and thumbnails show as empty blocks, so you can build the text first
and drop images in later.

Resize before committing:
  mogrify -resize 2400x2400\> -quality 85 hero-radiolarian.jpg
  mogrify -resize 900x900\>  -quality 85 oophila.jpg radiolarian.jpg
