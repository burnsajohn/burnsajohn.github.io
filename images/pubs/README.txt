COVER IMAGES FOR PUBLICATIONS
=============================

One image per paper, named with the slug that update_pubs.py suggests in the
comment above each entry in publications.yml. For example:

  2018-gene-based-predictive-models.jpg

Then uncomment the `image:` line for that entry. The assignment survives every
future run of the script.

Any paper without an image falls back to placeholder.svg, so the grid stays
even while you work through them.

Use a figure you made, not the publisher's typeset page. Landscape or square,
about 900 px on the long edge:

  mogrify -resize 900x900\> -quality 85 *.jpg

A note on rights: figures from your own open-access papers (CC BY) are yours to
reuse with attribution. For papers where you signed copyright over to the
publisher, your own figures are usually still reusable by the author, but the
publisher's typeset PDF page is not. When in doubt, use the pre-publication
version of your figure rather than the printed one.

Slugs are printed above each entry in publications.yml, e.g.

  # image slug: 2018-gene-based-predictive-models

so the file to create is images/pubs/2018-gene-based-predictive-models.jpg
