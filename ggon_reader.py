from PIL import Image, PngImagePlugin
import sys
import re

ggon = Image.open(sys.argv[1])
for i, k in ggon.text.items():
    if i == "Gang Garrison 2 Level Data":
        idx = re.search('{END ENTITIES', k).start()
        s = k[:idx]
        l = [x.strip() for x in s.split("},")]
        for j in l:
            print(j)
