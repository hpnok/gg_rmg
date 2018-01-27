import random
from PIL import Image, PngImagePlugin, ImageDraw
import glob
import os

#TODO: pick tiles (get tile info using a stronger prefix system) with a hierarchy ie if a fragment force both lane to the bottom one then there exist at least
#    one fragment of equal size that connect every part which can be swapped with the previous one
#    do checks like: if ll for x distance and all the ll segments are flat then add a palissade?(ll7.png) in the range
#    too many flat ss
#    too many cross/pit segments
#    air (transparent = (0, 0, 0, 0)
#    air solid bg = (255, 255, 255, 0) on blit with add flag solid parts becomes white (255, 255, 255, 255) while transparent takes the color of the bg
#    possibility to add a crate in a ll junction?
#    ll11 - ll13, ls8-ls14
#    if 2 section repeat or mirror repeat add at least one extension
#    flags: reusable, repeatable, (down/up)slope or (low/high/both/none)flat, allconnected/split/directiondependant, 
#TODO: use tiled pixel art background, color key the black part of the map around a fitting color for the theme
#TODO: use other color to mark ceiling (remove them to have a "open" map)
#TODO: have 1 oe 2 random color to remove/add some part of the map
#TODO: add a new rule of map fragment the "weird one" to prevent map being too funky or just prevent duplicate?
#TODO: 3cp
#TODO: add a flag to prevent rotation of some slice (like the stair in a one way pit), increase odds for "extensions", use argv to change map properties?
#https://www.saltycrane.com/blog/2007/12/how-to-pass-command-line-arguments-to/
#possible optimisations: everything
#get maps, improve the prefix system later
#what prevents a map from being taller then 300 pixels?

#colours used to identify connecting nodes and locators
purple = (163, 73, 164, 255)    # l side
blue = (0, 162, 232, 255)   # s side
gold = (255, 201, 14, 255)  # player spawn
red = (136, 0, 21, 255)    # medcab
oj = (244, 167, 85, 255)
tgrey = (195, 195, 195, 255)    # top of cap zone
bgrey = (127, 127, 127, 255)    # bot of cap zone
white = (255, 255, 255, 255)
black = (0, 0, 0, 255)

violet = (110, 10, 90, 255)
fgrey = (130, 145, 160, 255)

crop_odd = 0.5  # can be used to make the map more spacious


class MapFragment:
    def __init__(self, file_name):
        self.name = file_name
        self._image = None

        self.unique = False  # 1
        self.unflippable = False  # 2

        self.path_splitted = False  # 3
        self.one_way = False  # 3

        self.left_removable = False  # 4
        self.right_removable = False  # 4

        self.flat = False  # 5

    def load(self):
        if not self._image:
            i = Image.open(self.name)
            #self.image = i
            try:
                self.unique = (i.getpixel((0, 0)) != black)
                self.unflippable = (i.getpixel((1, 0)) != black)

                c = i.getpixel((2, 0))
                if c == fgrey:
                    self.path_splitted = True
                elif c != black:
                    self.one_way = True

                c = i.getpixel((3, 0))
                if c == fgrey:
                    self.left_removable = True
                    self.right_removable = True
                elif c == (218, 65, 54, 255):
                    self.left_removable = True
                elif c == (69, 117, 233, 255):
                    self.right_removable = True
                self.flat = (i.getpixel((4, 0)) != black)
            except IndexError:
                print("header errot on {}".format(self.name))
            self._image = i.crop((0, 1, i.width, i.height))

    @property
    def image(self):
        self.load()
        return self._image


class PointFragment(MapFragment):
    def __init__(self, file_name):
        super().__init__(file_name)

    def load(self):
        if not self._image:
            self._image = Image.open(self.name)


class Extension(MapFragment):
    def __init__(self, file_name, odd):
        super().__init__(file_name)
        self.length = 6
        self.odd = odd

seed = random.getrandbits(32)  # 32 bits seed added as the map name suffix
random.seed(seed)
os.chdir(os.getcwd() + "/RMG_resource")
spawnlist = []
lpointlist = []
spointlist = []
lllist = []
sslist = []
lslist = []
for file in glob.glob('*.png'):
    if file.startswith("spawn"):
        spawnlist.append(PointFragment(file))
    elif file.startswith("pl"):
        lpointlist.append(PointFragment(file))
    elif file.startswith("ps"):
        spointlist.append(PointFragment(file))
    elif file.startswith("ll"):
        lllist.append(MapFragment(file))
    elif file.startswith("ss"):
        sslist.append(MapFragment(file))
    elif file.startswith("ls"):
        lslist.append(MapFragment(file))

ss_ext = Extension("e1.png", 40)
sslist.append(ss_ext)  # an extension is still a valid segment
ll_ext = Extension("e2.png", 30)
lllist.append(ll_ext)


def pixel_height_in_column(image, x, color, start_y=0):
    height = image.height
    get = image.getpixel
    for y in range(start_y, height):
        if get((x, y)) == color:
            return y


def find_pixel_in_box(image, x0, y0, x1, y1, color):
    get = image.getpixel
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            if get((x, y)) == color:
                return x, y
    return None, None


def rightposition(image, colour):
    width, height = image.size
    band = image.crop((width-1, 0, width, height))
    for i, pixel in list(enumerate(band.getdata())):
        if pixel == colour:
            return i


def leftposition(image, colour):
    height = image.height
    band = image.crop((0, 0, 1, height))
    for i, pixel in list(enumerate(band.getdata())):
        if pixel == colour:
            return i


def findpixel(image, colour):
    width, height = image.size
    for i, pixel in list(enumerate(image.getdata())):
        if pixel == colour:
            yp, xp = divmod(i, width)
            return xp, yp


def crop_bot_path(map_image, double_check_left, double_check_right, left_x0, left_y0, right_x0, right_y0, left_height, right_height):
    get = map_image.getpixel
    try:
        if double_check_left:
            lx1, top1 = find_pixel_in_box(map_image, left_x0 + 1, left_y0 + 1, right_x0 - 1, left_y0 + left_height, violet)
            lx2, top2 = find_pixel_in_box(map_image, lx1 + 1, left_y0 + 1, right_x0 - 1, left_y0 + left_height, violet)
            if lx2 is None:
                lx, ltop = lx1, top1
            else:
                lx, ltop = lx2, top2
        else:
            lx, ltop = find_pixel_in_box(map_image, left_x0, left_y0, right_x0, left_y0 + left_height, violet)
        lbot = pixel_height_in_column(map_image, lx, violet, start_y=ltop + 1)
        if double_check_right:
            rx1, top1 = find_pixel_in_box(map_image, right_x0 + 1, right_y0 + 1, map_image.width - 1, right_y0 + right_height, violet)
            rx2, top2 = find_pixel_in_box(map_image, right_x0 + 1, right_y0 + 1, rx1 - 1, right_y0 + right_height, violet)
            if rx2 is None:
                rx, rtop = rx1, top1
            else:
                rx, rtop = rx2, top2
        else:
            rx, rtop = find_pixel_in_box(map_image, right_x0, right_y0, map_image.width - 1, right_y0 + right_height, violet)
        rbot = pixel_height_in_column(map_image, rx, violet, start_y=rtop + 1)
        y0 = max(ltop, rtop)
        y1 = min(lbot, rbot)
        if y1 - y0 > 5:
            draw = ImageDraw.Draw(map_image)
            draw.rectangle(((lx, y0), (rx, y1)), fill=white)
    except:
        print("crop error", seed)


def get_walk_mask(map_image):
    # walkmask compression algorithm from gg2 source adapted to simply convert white to non solid
    # bottom left pixel must be white for the decoder
    get = map_image.getpixel
    w, h = map_image.size
    c = get((0, h - 1))
    map_image.putpixel((0, h - 1), white)
    walkmask = '{WALKMASK}' + chr(10) + str(w) + chr(10) + "{}".format(h) + chr(10)
    fill = 0
    numv = 0
    for y in range(0, h):
        for x in range(0, w):
            numv <<= 1
            if get((x, y)) != white:
                if get((x, y)) == violet:  # TODO: spaghetti
                    map_image.putpixel((x, y), white)
                else:
                    numv += 1
            fill += 1
            if fill == 6:
                walkmask += chr(numv + 32)
                numv = 0
                fill = 0
    if fill > 0:
        for fill in range(fill, 6, 1):
            numv <<= 1
        walkmask += chr(numv + 32)
    walkmask += chr(10) + '{END WALKMASK}'
    map_image.putpixel((0, h - 1), c)
    return walkmask


spawn = random.choice(spawnlist)
segment_list = [spawn]
segment = spawn.image
koth = Image.new('RGBA', segment.size, black)
koth.paste(segment, (0, 0))
global_width = segment.width
short_top = True    # all spawns are ss connected
panic_counter = 0  # prevent picking too many times undesired segments
long_counter = 0
connected_counter = 0

previous_width = 0
previous_anchor = 0
crop = None

height_anchor = pixel_height_in_column(segment, global_width - 1, blue)
l = sslist + lslist

while global_width < 260 and l:
    extend = False
    flip = False
    s = random.choice(l)
    s.load()
    if not s.path_splitted:
        connected_counter += 1
        if panic_counter < 3 < connected_counter:
            l.remove(s)
            panic_counter += 1
            continue
    else:
        connected_counter = 0
    if short_top:
        if s.name.startswith("ss"):
            if not s.unflippable and random.randint(0, 1) == 1:
                segment = s.image.transpose(Image.FLIP_LEFT_RIGHT)
                flip = True
            else:
                segment = s.image
            if s.unique:
                sslist.remove(s)
        elif s.name.startswith("ls") and not s.unflippable:
            segment = s.image.transpose(Image.FLIP_LEFT_RIGHT)
            flip = True
            long_counter += 1
            if s.unique:
                lslist.remove(s)
        else:  # the piece can't be used remove it from the pool
            l.remove(s)
            panic_counter += 1
            continue
        if ss_ext.odd > random.randint(0, 99):
            global_width += ss_ext.length
            extend = True
        delta = pixel_height_in_column(segment, 0, blue)
    else:
        if s.name.startswith("ll"):
            if not s.unflippable and random.randint(0, 1) == 1:
                segment = s.image.transpose(Image.FLIP_LEFT_RIGHT)
                flip = True
            else:
                segment = s.image
            if s.unique:
                lllist.remove(s)
        else:
            segment = s.image
            if s.unique:
                lslist.remove(s)
        if ll_ext.odd > random.randint(0, 99):
            global_width += ll_ext.length
            extend = True
        delta = pixel_height_in_column(segment, 0, purple)
        long_counter += 1

    width = segment.width
    global_width += width
    koth = koth.crop((0, 0, global_width, 300))
    if extend:
        if short_top:
            koth.paste(ss_ext.image, (global_width - width - ss_ext.length, height_anchor))
        else:
            koth.paste(ll_ext.image, (global_width - width - ll_ext.length, height_anchor))
    koth.paste(segment, (global_width-width, height_anchor-delta))

    if crop:
        if flip:
            if s.right_removable:
                ps = segment_list[-1]
                crop_bot_path(koth, ps.left_removable == ps.right_removable, s.left_removable == s.right_removable,
                              previous_width - ps.image.width, previous_anchor, global_width - width, height_anchor, ps.image.height, segment.height)
        else:
            if s.left_removable:
                ps = segment_list[-1]
                crop_bot_path(koth, ps.left_removable == ps.right_removable, s.left_removable == s.right_removable,
                              previous_width - ps.image.width, previous_anchor, global_width - width, height_anchor, ps.image.height, segment.height)

    previous_anchor = height_anchor
    previous_width = global_width
    crop = False
    if flip:
        if s.left_removable:
            crop = True
    elif s.right_removable:
        crop = True

    pos = pixel_height_in_column(koth, global_width - 1, blue)
    if pos is None:
        short_top = False
        l = lllist + lslist
        height_anchor = pixel_height_in_column(koth, global_width - 1, purple)
    else:
        short_top = True
        l = sslist + lslist
        height_anchor = pos
    #koth.show()
    segment_list.append(s)
    panic_counter = 0

extend = False
delta = 0
if short_top:
    s = random.choice(spointlist)
    segment = s.image
    delta = pixel_height_in_column(segment, 0, blue)
    if ss_ext.odd > random.randint(0, 99):
        global_width += ss_ext.length
        extend = True
else:
    s = random.choice(lpointlist)
    segment = s.image
    delta = pixel_height_in_column(segment, 0, purple)
    if ll_ext.odd > random.randint(0, 99):
        global_width += ll_ext.length
        extend = True
#add the point
width = segment.width
global_width += width
koth = koth.crop((0, 0, global_width, 300))
if extend:
    if short_top:
        koth.paste(ss_ext.image, (global_width - width - ss_ext.length, height_anchor))
    else:
        koth.paste(ll_ext.image, (global_width - width - ll_ext.length, height_anchor))
#draft = Image.new('RGBA', (global_width, 300), black)
#draft.paste(koth, (0, 0))


#draft = koth.crop((0, 0, global_width, 300))
koth.paste(segment, (global_width-width, height_anchor-delta))

#cut black border
maxx, maxy = findpixel(koth, white)
reverseddraft = koth.transpose(Image.FLIP_TOP_BOTTOM)
reverseddraft.putpixel((0, 0), black)
minx, miny = findpixel(reverseddraft, white)
if maxy < 5:
    maxy = 5
if miny < 8:
    miny = 8
cropddraft = koth.crop((0, maxy - 5, global_width, 300 - miny + 8))
global_height = cropddraft.height

#get capture point here and turn pixel locators white
toppx, toppy = find_pixel_in_box(cropddraft, global_width - width, 0, global_width - 1, global_height - 1, tgrey)
cropddraft.putpixel((toppx, toppy), white)
botpy = pixel_height_in_column(cropddraft, toppx, bgrey)
cropddraft.putpixel((toppx, botpy), white)

#final layout, add mirrored half
koth = koth.crop((0, 0, 2*global_width, global_height))
koth.paste(cropddraft, (0, 0))
koth.paste(cropddraft.transpose(Image.FLIP_LEFT_RIGHT), (global_width, 0))

#red entities
spawn_width = spawn.image.width
entities = '{ENTITIES}' + chr(10) + '[' + '{background:ffffff,type:meta,void:000000}'
spawnx, spawny = find_pixel_in_box(koth, 2, 0, spawn_width - 1, global_height - 1, gold)
entities += ',{' + 'type:redspawn,x:{},y:{}'.format(spawnx*6, spawny*6-32) + '}'
entities += ',{' + 'type:redspawn,x:{},y:{}'.format(spawnx*6 + 36, spawny*6-32) + '}'
entities += ',{' + 'type:redspawn,x:{},y:{}'.format(spawnx*6 + 72, spawny*6-32) + '}'
cabx, caby = find_pixel_in_box(koth, 2, 0, spawn_width - 1, global_height - 1, red)
entities += ',{' + 'type:medCabinet,x:{},y:{}'.format(cabx*6 + 6, caby*6-48) + '}'
entities += ',{' + 'type:spawnroom,x:0,xscale:{:.2f},y:0,yscale:{:2f}'.format((spawn_width-2)/7, (global_height - 1)/7) + '}'
entities += ',{' + 'type:redteamgate,x:{},xscale:3,y:0,yscale:{:2f}'.format((spawn_width-2)*6, global_height/10) + '}'
#koth entities
entities += ',{' + 'type:KothControlPoint,x:{},y:{}'.format(global_width*6, (toppy + botpy)*3) + '}'
entities += ',{' + 'type:CapturePoint,x:{},xscale:{:.2f},y:{},yscale:{:.2f}'.format(toppx*6, (global_width - toppx)*2/7, toppy*6, (botpy - toppy)/7) + '}'
global_width *= 2
entities += ',{' + 'type:bluespawn,x:{},y:{}'.format((global_width-spawnx)*6, spawny*6-32) + '}'
entities += ',{' + 'type:bluespawn,x:{},y:{}'.format((global_width-spawnx)*6 - 36, spawny*6-32) + '}'
entities += ',{' + 'type:bluespawn,x:{},y:{}'.format((global_width-spawnx)*6 - 72, spawny*6-32) + '}'
entities += ',{' + 'type:medCabinet,x:{},y:{}'.format((global_width-cabx-6)*6, caby*6-48) + '}'
entities += ',{' + 'type:spawnroom,x:{},xscale:{:.2f},y:0,yscale:{:2f}'.format((global_width - spawn_width + 2)*6, (spawn_width - 2)/7, (global_height - 1)/7) + '}'
entities += ',{' + 'type:blueteamgate,x:{},xscale:3,y:0,yscale:{:2f}'.format((global_width - spawn_width - 1)*6, global_height/10) + '}]' + chr(10)
entities += '{END ENTITIES}'

walkmask = get_walk_mask(koth)

#recolour n stuff
koth.putpixel((0, global_height-1), black)
medcab = Image.open("medcab.png")
koth.paste(medcab, (cabx, caby - 9))
koth.paste(medcab, (global_width - cabx - 7, caby - 9))
door = Image.open("door.png")
dh = pixel_height_in_column(koth, spawn_width - 1, blue)
koth.paste(door, (spawn_width - 1, dh))
door = door.transpose(Image.FLIP_LEFT_RIGHT)
koth.paste(door, (global_width - spawn_width - 1, dh))
# imageops.colorize needs type L (black/white) images
# randomgreys
rsgrey = (random.randrange(146, 154), random.randrange(140, 148), random.randrange(135, 145), 255)
rgrey = (random.randrange(152, 163), random.randrange(152, 163), random.randrange(152, 163), 255)
(rgr, rgg, rgb, rgs) = rgrey
bsgrey = (random.randrange(134, 142), random.randrange(142, 147), random.randrange(146, 150), 255)
get = koth.getpixel
put = koth.putpixel
for y in range(1, global_height-1):
    for x in range(1, spawn_width - 1):
        if get((x, y)) == white:
            put((x, y), rsgrey)
            put((global_width - x - 1, y), bsgrey)
            if spawny - 7 < y < spawny - 3:    # 139 < y < 143
                put((x, y), (167, 99, 97, 255))
                put((global_width - x - 1, y), (97, 129, 167, 255))
    for x in range(spawn_width + 1, global_width//2):
        if get((x, y)) == white:
            if y < 4:
                put((x, y), ((rgr - 10), (rgg - 10), (rgb - 10), 255))
                put((global_width - x - 1, y), ((rgr - 10), (rgg - 10), (rgb - 10), 255))
            elif y < 21:
                put((x, y), ((rgr - 6), (rgg - 6), (rgb - 6), 255))
                put((global_width - x - 1, y), ((rgr - 6), (rgg - 6), (rgb - 6), 255))
            elif y < 39:
                put((x, y), ((rgr - 3), (rgg - 3), (rgb - 3), 255))
                put((global_width - x - 1, y), ((rgr - 3), (rgg - 3), (rgb - 3), 255))
            else:
                put((x, y), rgrey)
                put((global_width - x - 1, y), rgrey)
        elif get((x, y)) == oj:  # ground around point
            if (x + y) % 3 != 0:
                put((x, y), black)
            if (global_width - x - 1 + y) % 3 != 0:
                put((global_width - x - 1, y), black)
metadata = PngImagePlugin.PngInfo()
metadata.add_text('Gang Garrison 2 Level Data', entities+walkmask)
os.chdir(os.getcwd()[:-13]+"/Maps")
mapname = "koth_random_{}.png".format(seed)
koth = koth.convert('RGB')
#koth.show()
koth.save(mapname, "png", optimize=True, pnginfo=metadata)
#newmap = Image.open("koth_random.png")
#print(newmap.text)
#ggon = Image.open("a5.png")
#print(ggon.text)
os.chdir(os.getcwd()[:-5])
file = open("randomname.gg2", "w")
file.write(mapname[:-4])
file.close()

