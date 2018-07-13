import random
from PIL import Image, PngImagePlugin, ImageDraw
import glob
import os
import sys

#TODO: pick tiles (get tile info using a stronger prefix system) with a hierarchy ie if a fragment force both lane to the bottom one then there exist at least
#    one fragment of equal size that connect every part which can be swapped with the previous one
#    possibility to add a crate in a ll junction?
#    ll11 - ll13, ls8-ls14
#    if 2 section repeat or mirror repeat add at least one extension
#    flags: reusable, repeatable, (down/up)slope or (low/high/both/none)flat, allconnected/split/directiondependant,
#TODO: use other color to mark ceiling (remove them to have a "open" map)
#TODO: have 1 oe 2 random color to remove/add some part of the map
#what prevents a map from being taller then 300 pixels?

#colours used to identify connecting nodes and locators
purple = (163, 73, 164, 255)    # l side
blue = (0, 162, 232, 255)   # s side
door_yellow = (255, 243, 0, 255)
door_orange = (255, 127, 39, 255)
gold = (255, 201, 14, 255)  # player spawn
red = (136, 0, 21, 255)    # medcab
oj = (244, 167, 85, 255)
#tgrey = (195, 195, 195, 254)    # top of cap zone
pgrey = (127, 127, 127)    # bot of cap zone
white = (255, 255, 255, 255)
black = (0, 0, 0, 255)

crp_px = (198, 44, 90, 200)
fgrey = (130, 145, 160, 255)

air_wall = (56, 74, 188, 200)
air_air = (255, 255, 255, 0)

#TODO: use style to remove ceiling or not?
style = [
    ("CS", (28, 34, 22)),
    ("IN", (-45, -38, -50)),
    ("MN", (-28, -33, -34)),
    ("SC", (22, 23, 11)),
    ("CF", (4, 10, 6)),
    ("BD", (-44, -34, -36))
    ]

MODE = "KOTH"
length_max = 250
if len(sys.argv) > 1:
    if sys.argv[1] == "CP":
        MODE = "CP"
        length_max = 230
    elif sys.argv[1] == "DKOTH":
        MODE = "DKOTH"
        length_max = 180

flat_distance_threshold = 49  # assume average segment length is 20
not_flat_distance_threshold = 130
flat_saviors = []
panic_threshold = 9

spawnlist = []
lpointlist = []
spointlist = []
lllist = []
sslist = []
lslist = []


class Fragment:
    def __init__(self, file_name):
        self.name = file_name
        self._image = None

        self.unique = False  # 1
        self.flip_locked = False  # 2

        self.path_split = -1  # 3  # TODO:-1 , 0, +1 modulate the value of connected counter, 0 allow excluding small connecting pieces
        self.one_way = False  # 3

        self.left_removable = False  # 4
        self.right_removable = False  # 4

        self.flat = False  # 5

        self.lc = blue
        self.rc = blue

    def load(self):
        if not self._image:
            self._image = Image.open(self.name)

    @property
    def image(self):
        self.load()
        return self._image

#TODO: special ss fragment for cp points (ss or ll)
class MapFragment(Fragment):
    def __init__(self, file_name):
        super().__init__(file_name)
        self.pars_file_name(file_name)

    def pars_file_name(self, file_name):
        """file name structure:
           0:p/l left side connection
           1:p/l right side connection
           2:u/- unique
           3:l/- flip locked prevent the fragment from being flipped horizontally
           4:s/o/c- path is split (not connected) or one way (not all direction are possible) or a connector (small segment)
           5:l/r/b/- can crop the bottom path on left/right/both side
           6:f/- flat"""
        if file_name[0] == 'l':
            self.lc = purple
        if file_name[1] == 'l':
            self.rc = purple
        if file_name[2] == 'u':
            self.unique = True
        if file_name[3] == 'l':
            self.flip_locked = True
        connexion_type = file_name[4]
        if connexion_type == 's':
            self.path_split = 1
        elif connexion_type == 'o':
            self.path_split = -1
            self.one_way = True
        elif connexion_type == 'c':
            self.path_split = 0
        crop_side = file_name[5]
        if crop_side == 'l':
            self.left_removable = True
        elif crop_side == 'r':
            self.right_removable = True
        elif crop_side == 'b':
            self.left_removable = True
            self.right_removable = True
        if file_name[6] == 'f':
            self.flat = True
        else:
            if self.lc != self.rc:
                flat_saviors.append(self)


class PointFragment(Fragment):
    def __init__(self, file_name):
        super().__init__(file_name)
        self.name = file_name
        self._image = None
        if file_name[1] == 'l':
            self.lc = purple  # considered as ls for ceiling crop
        elif file_name.startswith("spawn"):
            self.rc = blue


class Extension(MapFragment):
    def __init__(self, file_name, odd, left_color, right_color):
        super().__init__(file_name)
        self.length = 6
        self.odd = odd
        self.lc = left_color
        self.rc = right_color


class Segment:
    def __init__(self, fragment, reverse, x, remove_ceiling, extension=None):
        self.f = fragment
        self.ext = extension
        self.reversed = reverse
        self.x = x
        self.y = 0
        self.crop_s = None
        self.door_dot = []  # left and right position of the door dot on the image
        self.remove_ceil = remove_ceiling

    def get_image(self):
        if self.reversed:
            return self.f.image.transpose(Image.FLIP_LEFT_RIGHT)
        return self.f.image

    def crop(self, map_image):
        if not self.crop_s:
            return
        get = map_image.getpixel
        left = self.crop_s
        right = self
        lw, lh = left.f.image.size
        rw, rh = self.f.image.size
        try:
            if left.f.left_removable == left.f.right_removable:  # must check for 2 pairs
                lx1, top1 = find_pixel_in_box(map_image, left.x + 1, left.y + 1, left.x + lw, left.y + lh, crp_px)
                lx2, top2 = find_pixel_in_box(map_image, lx1 + 1, top1, left.x + lw - 1, left.y + lh, crp_px)
                if lx2 is None:  # there was no pixel to the right of the first one, then the first one found was the rightmost one
                    lx, ltop = lx1, top1
                else:
                    lx, ltop = lx2, top2
            else:
                lx, ltop = find_pixel_in_box(map_image, left.x, left.y, left.x + lw, left.y + lh, crp_px)
            lbot = pixel_height_in_column(map_image, lx, crp_px, start_y=ltop + 1)

            if right.f.left_removable == right.f.right_removable:
                rx1, top1 = find_pixel_in_box(map_image, right.x + 1, right.y + 1, right.x + rw - 1, right.y + rh, crp_px)
                rx2, top2 = find_pixel_in_box(map_image, right.x + 1, top1, rx1 - 1, right.y + rh, crp_px)
                if rx2 is None:
                    rx, rtop = rx1, top1
                else:
                    rx, rtop = rx2, top2
            else:
                rx, rtop = find_pixel_in_box(map_image, right.x, right.y, right.x + rw - 1, right.y + rh, crp_px)
            rbot = pixel_height_in_column(map_image, rx, crp_px, start_y=rtop + 1)

            y0 = max(ltop, rtop)
            y1 = min(lbot, rbot)
            if y1 - y0 > 6:
                draw = ImageDraw.Draw(map_image)
                draw.rectangle(((lx, y0), (rx, y1)), fill=air_wall)
                for f in segment_list.l:  # add nice dot to show fragment slice
                    dx = f.x - 1
                    if dx < lx:
                        continue
                    if dx >= rx:
                        break
                    if get((dx, y0 - 1)) == black:
                        map_image.putpixel((dx, y0 - 1), door_yellow)
                    if get((dx + 1, y0 - 1)) == black:
                        map_image.putpixel((dx + 1, y0 - 1), door_yellow)
                    if get((dx, y1 + 1)) == black:
                        map_image.putpixel((dx, y1 + 1), door_orange)
                    if get((dx + 1, y1 + 1)) == black:
                        map_image.putpixel((dx + 1, y1 + 1), door_orange)
        except:
            print("crop error", seed)
            raise IndexError


class SegmentList:
    def __init__(self):
        self.l = []
        self.previous_crop = False
        self.spawn = None

    def get_prev_non_ext(self):
        for i in reversed(self.l):
            if not i.ext:
                return i
        return None

    def get_next_non_ext(self, start):
        for i in range(start, len(self.l)):
            if not self.l[i].ext:
                return self.l[i]
        return None

    def push(self, segment, crop_left, crop_right):
        if not self.spawn:
            self.l.append(segment)
            self.spawn = segment
        else:
            if not segment.ext:
                if self.previous_crop and crop_left:
                    segment.crop_s = self.get_prev_non_ext()
                self.previous_crop = crop_right
            self.l.append(segment)

    def build_map(self, g_width):
        map_image = Image.new('RGBA', (g_width, 300), black)
        it = iter(self.l)
        i = next(it)  # spawn
        y = 0
        map_image.paste(i.f.image, (0, 0))
        cr = blue
        try:
            while True:
                # the position of the previous "door dot", spawn are always short on top
                height_anchor = pixel_height_in_column(map_image, i.x + i.f.image.width - 1, cr, start_y=i.y)
                #if not height_anchor:
                #    height_anchor = i.y + delta
                i.door_dot.append(height_anchor)
                i = next(it)
                if i.reversed:
                    cl, cr = i.f.rc, i.f.lc
                else:
                    cl, cr = i.f.lc, i.f.rc
                im = i.get_image()
                delta = pixel_height_in_column(im, 0, cl)  # the position of the current "door dot" to be matched with the previous on
                #if not delta:
                #    delta = height_anchor - y
                i.door_dot.append(height_anchor)
                try:
                    y = height_anchor - delta
                except TypeError:
                    pass
                i.y = y
                map_image.paste(im, (i.x, y))
                i.crop(map_image)
                #map_image.show()
        except StopIteration:
            pass
        return map_image

    def insert_at(self, segment, index, crop_left, crop_right):
        #TODO: support crop from left to right?
        if index >= len(self.l):
            self.push(segment, crop_left, crop_right)
            return segment.f.image.width
        else:
            next_s = self.get_next_non_ext(index)
            if next_s:
                if next_s.crop_s:
                    if crop_left:
                        segment.crop_s = next_s.crop_s
                    if crop_right:
                        next_s.crop_s = segment
                    else:
                        next_s.crop_s = None
            current = self.l[index]
            segment.x = current.x
            if segment.reversed:
                if segment.f.rc == purple:
                    segment.remove_ceil = current.remove_ceil
            else:
                if segment.f.lc == purple:
                    segment.remove_ceil = current.remove_ceil
            self.l.insert(index, segment)
            dx = segment.f.image.width
            for i in range(index + 1, len(self.l)):  # adjust position of next segments
                self.l[i].x += dx
            return dx

    def remove_ceiling(self, map_image, ceiling_height):
        get = map_image.getpixel
        for i in self.l:
            if i.remove_ceil:
                if i.f.lc != i.f.rc:  #ls
                    if i.reversed:  #sl
                        r = i.x + i.f.image.width - 1
                        bot = i.door_dot[1]
                        l = r
                        for l in range(r - 1, i.x, -1):
                            if get((l, bot)) == purple:
                                break
                    else:
                        l = i.x
                        bot = i.door_dot[0]
                        r = None
                        for x in range(l + 1, i.x + i.f.image.width - 1):
                            if get((x, bot)) == purple:
                                r = x
                                break
                        if not r:
                            r = i.x + 2*i.f.image.width - 1  # spaghetti for cp/dkoth maps
                else:
                    #if i.door_dot[1]:
                    #try:
                    bot = max(i.door_dot)
                    #except TypeError:
                    #    pass
                    #else:
                    #    bot = i.door_dot[0]
                    l = i.x
                    r = l + i.f.image.width - 1
                draw = ImageDraw.Draw(map_image)
                draw.rectangle(((l, ceiling_height), (r, bot)), fill=air_air)


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


def find_cap_zone(image, x0, y0, x1, y1):
    get = image.getpixel
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            if get((x, y))[:3] == pgrey:
                for yp in range(y + 1, y1 + 1):
                    if get((x, yp))[:3] == pgrey:
                        if get((x, y))[3] == 200:
                            image.putpixel((x, y), air_wall)
                        else:
                            image.putpixel((x, y), air_air)
                        if get((x, yp))[3] == 200:
                            image.putpixel((x, yp), air_wall)
                        else:
                            image.putpixel((x, yp), air_air)
                        return x, y, yp
                return x, y, y1 + 1
    return None, None, None


def findpixel(image, colour):
    width, height = image.size
    for i, pixel in enumerate(image.getdata()):
        if pixel == colour:
            yp, xp = divmod(i, width)
            return xp, yp


def findFirstNonSolid(image):
    width, height = image.size
    for i, pixel in enumerate(image.getdata()):
        if pixel[3] < 255:
            yp, xp = divmod(i, width)
            return xp, yp


def get_walk_mask(map_image):
    # walkmask compression algorithm from gg2 source adapted to simply convert white to non solid
    # bottom left pixel must be white for the decoder
    get = map_image.getpixel
    w, h = map_image.size
    c = get((0, h - 1))
    map_image.putpixel((0, h - 1), (255, 255, 255, 0))
    walkmask = '{WALKMASK}' + chr(10) + str(w) + chr(10) + "{}".format(h) + chr(10)
    fill = 0
    numv = 0
    for i, pixel in enumerate(map_image.getdata()):
        numv <<= 1
        if pixel[3] == 255:
            numv += 1
        fill += 1
        if fill == 6:
            walkmask += chr(numv + 32)
            numv = 0
            fill = 0
    """for y in range(0, h):
        for x in range(0, w):
            numv <<= 1
            if get((x, y))[3] == 255:
                #if get((x, y)) == crp_px:  # TODO: spaghetti
                #    map_image.putpixel((x, y), white)
                #else:
                numv += 1
            fill += 1
            if fill == 6:
                walkmask += chr(numv + 32)
                numv = 0
                fill = 0"""
    if fill > 0:
        for fill in range(fill, 6, 1):
            numv <<= 1
        walkmask += chr(numv + 32)
    walkmask += chr(10) + '{END WALKMASK}'
    map_image.putpixel((0, h - 1), c)
    return walkmask


def add_bg(map_image, bg_file_name, sw):
    im = Image.open("bg/" + bg_file_name + ".png")
    bw, bh = im.size
    w, h = map_image.size
    b = Image.new('RGBA', (w, h), im.getpixel((0, bh - 1)))
    if bw < w - 2*sw:
        x = sw
        while x < w - 2*sw:
            b.paste(im, (x, 0))
            x += bw
        bw = w - 2*sw
    else:
        b.paste(im, ((w - 2*sw - bw)//2 + sw, 0))
    b.alpha_composite(map_image)
    #b.show()
    return b

seed = random.getrandbits(32)  # 32 bits seed added as the map name suffix
#seed = 3239445057
#seed = 2887880279  # flat
random.seed(seed)
print(seed)
os.chdir(os.getcwd() + "/RMG_resource")
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

ss_ext = Extension("ee--c-f1.png", 35, blue, blue)
sslist.append(ss_ext)  # an extension is still a valid segment
ll_ext = Extension("ee--c-f2.png", 30, purple, purple)
lllist.append(ll_ext)
ls_ext = Extension("ee--c-f3.png", 30, purple, blue)
lslist.append(ls_ext)

spawn = random.choice(spawnlist)
#segment_list = [spawn]
#segment = spawn.image
#koth = Image.new('RGBA', segment.size, black)
#koth.paste(segment, (0, 0))
global_width = spawn.image.width
short_top = True    # all spawns are ss connected
panic_counter = 0  # prevent picking too many times undesired segments
long_counter = 0
flat_counter = 0
connected_counter = 1
door_position = []  # list of door location
remove_ceiling = False
segment_list = SegmentList()
segment_list.push(Segment(spawn, False, 0, False, extension=True), False, False)
#map_seg = [Segment(spawn, False, 0)]

previous_width = 0
previous_anchor = 0

if MODE == "KOTH":
    l = sslist + lslist
else:
    l = [ls_ext]

while global_width < length_max and l:
    extend = None
    flip = False
    s = random.choice(l)
    prev_c_count = connected_counter
    prev_remove_ceil = remove_ceiling  # used for extension
    next_remove_ceiling = remove_ceiling
    # pick a piece, check if it fits the desired sequence, if not remove it from the pool
    if s.path_split > 0:  # not split
        connected_counter += s.path_split
        if panic_counter < panic_threshold and 2 <= connected_counter:
            print("not split pop")
            l.remove(s)
            panic_counter += 1
            continue
    elif s.path_split < 0:
        if connected_counter > 0:
            connected_counter = 0
        else:
            connected_counter += s.path_split
            if panic_counter < panic_threshold and connected_counter <= -3:
                print("split pop")
                l.remove(s)
                panic_counter += 1
                continue
    if s.flat:
        if flat_counter <= 0:
            flat_counter = global_width - 1  # using global width factor in extensions too
        if panic_counter >= panic_threshold:  # prevent map from being too flat by forcing a segment
            s = MapFragment(random.choice(flat_saviors))  # a ls frag which isn't flat
            flat_counter = 0
            print("too flat savior")
        elif flat_distance_threshold <= global_width - flat_counter:
            print("too flat pop")
            l.remove(s)
            panic_counter += 1
            connected_counter = prev_c_count
            continue
    else:
        if flat_counter >= 0:
            flat_counter = -global_width + 1
        if panic_counter < panic_threshold//2 and global_width + flat_counter >= not_flat_distance_threshold:
            print("not flat pop")
            l.remove(s)
            panic_counter += 1
            connected_counter = prev_c_count
            continue
    if short_top:
        if s.lc == s.rc:  #ss
            if not s.flip_locked and random.randint(0, 1) == 1:
                flip = True
            if s.unique:
                sslist.remove(s)
        elif s.lc == purple and not s.flip_locked:  #ls
            short_top = False
            flip = True
            if 75 > random.randint(0, 99):
                remove_ceiling = True
                next_remove_ceiling = True
            long_counter += 1
            if s.unique:
                lslist.remove(s)
        else:  # the piece can't be used remove it from the pool
            l.remove(s)
            panic_counter += 1
            continue
        if (ss_ext.odd + 10*connected_counter) > random.randint(0, 99):
            extend = ss_ext
    else:
        if s.lc == s.rc:  #ll
            if not s.flip_locked and random.randint(0, 1) == 1:
                flip = True
            if s.unique:
                lllist.remove(s)
        else:  #ls
            short_top = True
            next_remove_ceiling = False
            if s.unique:
                lslist.remove(s)
        if (ll_ext.odd + 10*connected_counter) > random.randint(0, 99):
            extend = ll_ext
        long_counter += 1

    if extend:
        door_position.append(global_width - 1)
        segment_list.push(Segment(extend, False, global_width, prev_remove_ceil, extension=True), False, False)
        global_width += extend.length

    door_position.append(global_width - 1)
    if flip:
        cl, cr = s.right_removable, s.left_removable
    else:
        cl, cr = s.left_removable, s.right_removable
    segment_list.push(Segment(s, flip, global_width, remove_ceiling, extension=s.name.startswith("ee")), cl, cr)
    global_width += s.image.width

    if short_top:
        l = sslist + lslist
    else:
        l = lllist + lslist
    panic_counter = 0
    remove_ceiling = next_remove_ceiling

#add the points
idx = 3
if MODE == "CP" or MODE == "DKOTH":
    try:
        while segment_list.l[idx].x - spawn.image.width < 60:
            idx += 1
    except IndexError:
        idx -= 1
    s = segment_list.l[idx]
    if s.reversed:
        if s.f.rc == blue:
            s = random.choice(spointlist)
        else:
            s = random.choice(lpointlist)
    else:
        if s.f.lc == blue:
            s = random.choice(spointlist)
        else:
            s = random.choice(lpointlist)
    global_width += segment_list.insert_at(Segment(s, False, global_width, False), idx, False, False)
    global_width += segment_list.insert_at(Segment(s, True, global_width, False), idx + 1, False, False)

if MODE != "DKOTH":
    extend = None
    if short_top:
        s = random.choice(spointlist)
        if ss_ext.odd > random.randint(0, 99):
            extend = ss_ext
    else:
        s = random.choice(lpointlist)
        if ll_ext.odd > random.randint(0, 99):
            extend = ll_ext

    if extend:
        door_position.append(global_width - 1)
        segment_list.push(Segment(extend, False, global_width, remove_ceiling, extension=True), False, False)
        global_width += extend.length

    door_position.append(global_width - 1)
    segment_list.push(Segment(s, False, global_width, remove_ceiling), False, False)
    global_width += s.image.width

koth = segment_list.build_map(global_width)

#cut black border
maxx, maxy = findFirstNonSolid(koth)
reverseddraft = koth.transpose(Image.FLIP_TOP_BOTTOM)
reverseddraft.putpixel((0, 0), black)
minx, miny = findFirstNonSolid(reverseddraft)
try:
    segment_list.remove_ceiling(koth, maxy - 8)
except AttributeError:
    pass
if maxy < 8:
    maxy = 8
if miny < 20:
    miny = 20
cropddraft = koth.crop((0, maxy - 8, global_width, 300 - miny + 20))
global_height = cropddraft.height

#get capture point
if MODE != "KOTH":
    cppx, ctpy, cbpy = find_cap_zone(cropddraft, segment_list.l[idx].x + 1, 0, segment_list.l[idx + 1].x - 1, global_height - 1)
    rx = 2*segment_list.l[idx + 1].x - cppx - 1
    v = cropddraft.getpixel((cppx, ctpy))
    cropddraft.putpixel((rx, ctpy), v)
    v = cropddraft.getpixel((cppx, cbpy))
    cropddraft.putpixel((rx, cbpy), v)
if MODE != "DKOTH":
    toppx, toppy, botpy = find_cap_zone(cropddraft, global_width - segment_list.l[-1].f.image.width, 0, global_width - 1, global_height - 1)

#final layout, add mirrored half
koth = koth.crop((0, 0, 2*global_width, global_height))
koth.paste(cropddraft, (0, 0))
koth.paste(cropddraft.transpose(Image.FLIP_LEFT_RIGHT), (global_width, 0))

#red spawn entities
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
#entities
if MODE == "CP":
    entities += ',{' + 'type:controlPoint1,x:{},y:{}'.format(segment_list.l[idx + 1].x*6, (ctpy + cbpy)*3) + '}'
    entities += ',{' + 'type:CapturePoint,x:{},xscale:{:.2f},y:{},yscale:{:.2f}'.format(cppx*6, (segment_list.l[idx + 1].x - cppx)*2/7, ctpy*6, (cbpy - ctpy)/7) + '}'
    entities += ',{' + 'type:controlPoint2,x:{},y:{}'.format(global_width*6, (toppy + botpy)*3) + '}'
    entities += ',{' + 'type:CapturePoint,x:{},xscale:{:.2f},y:{},yscale:{:.2f}'.format(toppx*6, (global_width - toppx)*2/7, toppy*6, (botpy - toppy)/7) + '}'
    global_width *= 2
    entities += ',{' + 'type:controlPoint3,x:{},y:{}'.format((global_width - segment_list.l[idx + 1].x)*6, (ctpy + cbpy)*3) + '}'
    entities += ',{' + 'type:CapturePoint,x:{},xscale:{:.2f},y:{},yscale:{:.2f}'.format((global_width - 1 - rx)*6, (segment_list.l[idx + 1].x - cppx)*2/7, ctpy*6, (cbpy - ctpy)/7) + '}'
elif MODE == "DKOTH":
    entities += ',{' + 'type:KothRedControlPoint,x:{},y:{}'.format(segment_list.l[idx + 1].x*6, (ctpy + cbpy)*3) + '}'
    entities += ',{' + 'type:CapturePoint,x:{},xscale:{:.2f},y:{},yscale:{:.2f}'.format(cppx*6, (segment_list.l[idx + 1].x - cppx)*2/7, ctpy*6, (cbpy - ctpy)/7) + '}'
    global_width *= 2
    entities += ',{' + 'type:KothBlueControlPoint,x:{},y:{}'.format((global_width - segment_list.l[idx + 1].x)*6, (ctpy + cbpy)*3) + '}'
    entities += ',{' + 'type:CapturePoint,x:{},xscale:{:.2f},y:{},yscale:{:.2f}'.format((global_width - 1 - rx)*6, (segment_list.l[idx + 1].x - cppx)*2/7, ctpy*6, (cbpy - ctpy)/7) + '}'
else:
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
selected_style = random.choice(style)
rsgrey = (random.randrange(176, 183) + selected_style[1][0]//2,
          random.randrange(174, 179) + selected_style[1][1]//2,
          random.randrange(167, 175) + selected_style[1][2]//2, 255)
rgrey = (random.randrange(144, 149) + selected_style[1][0],
         random.randrange(144, 149) + selected_style[1][1],
         random.randrange(144, 149) + selected_style[1][2], 255)
(rgr, rgg, rgb, rgs) = rgrey
bsgrey = (random.randrange(177, 184) + selected_style[1][0]//2,
          random.randrange(185, 189) + selected_style[1][1]//2,
          random.randrange(186, 190) + selected_style[1][2]//2, 255)
get = koth.getpixel
put = koth.putpixel
for y in range(8, global_height-17):
    if y == 17:
        rgrey = (rgr + 4, rgg + 4, rgb + 4, 255)
    if y == 32:
        rgrey = (rgr + 7, rgg + 7, rgb + 7, 255)
    elif y == 50:
        rgrey = (rgr + 10, rgg + 10, rgb + 10, 255)
    for x in range(1, spawn_width - 1):
        if get((x, y))[3] == 200:
            if spawny - 7 < y < spawny - 3:    # 139 < y < 143
                put((x, y), (175, 99, 97, 255))
                put((global_width - x - 1, y), (97, 129, 176, 255))
            else:
                put((x, y), rsgrey)
                put((global_width - x - 1, y), bsgrey)
    for x in range(spawn_width + 1, global_width//2):
        if get((x, y))[3] == 200:
            put((x, y), rgrey)
            put((global_width - x - 1, y), rgrey)
        elif get((x, y)) == oj:  # ground around point
            if (x + y) % 3 != 0:
                put((x, y), black)
            if (global_width - x - 1 + y) % 3 != 0:
                put((global_width - x - 1, y), black)
koth = add_bg(koth, selected_style[0], spawn_width)
metadata = PngImagePlugin.PngInfo()
metadata.add_text('Gang Garrison 2 Level Data', entities+walkmask, zip=True)
os.chdir(os.getcwd()[:-13]+"/Maps")
mapname = "{}_random_{}.png".format(MODE.lower(), seed)
koth = koth.convert('RGB')
#koth.show()
koth.save(mapname, "png", optimize=True, pnginfo=metadata)
os.chdir(os.getcwd()[:-5])
file = open("randomname.gg2", "w")
file.write(mapname[:-4])
file.close()

