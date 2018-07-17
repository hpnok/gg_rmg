from PIL import Image
import glob
import os
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


def check_fragment(file_name):
    print("checking " + file_name)
    image = Image.open(file_name)
    w, h = image.size
    if file_name[0] == 's':
        y = pixel_height_in_column(image, 0, blue)
        if not 0 <= y < h:
            print(file_name + " left pixel (blue) not found")
    elif file_name[0] == 'l':
        y = pixel_height_in_column(image, 0, purple)
        if not 0 <= y < h:
            print(file_name + " left pixel (purple) not found")
    if file_name[1] == 's':
        y = pixel_height_in_column(image, w - 1, blue)
        if not 0 <= y < h:
            print(file_name + " right pixel (blue) not found")
    elif file_name[1] == 'l':
        y = pixel_height_in_column(image, w - 1, purple)
        if not 0 <= y < h:
            print(file_name + " right pixel (purple) not found")
    if file_name[5] != '-':
        x, y = find_pixel_in_box(image, 0, 0, w - 1, h - 1, crp_px)
        if x is None:
            print(file_name + " couldn't find crop pointer")
            return
        yy = pixel_height_in_column(image, x, crp_px, y + 1)
        if yy is None:
            print(file_name + " couldn't find matching crop pointer on line x = " + str(x))
            return
        if file_name[5] == 'b':
            lx, ly = find_pixel_in_box(image, 0, 0, x - 1, h - 1, crp_px)
            rx, ry = find_pixel_in_box(image, x + 1, 0, w - 1, h - 1, crp_px)
            if lx is None and rx is None:
                print(file_name + " couldn't find second crop pointer")
            elif lx is not None:
                ly = pixel_height_in_column(image, lx, crp_px, ly + 1)
                if ly is None:
                    print(file_name + " couldn't find second matching crop pointer on line x = " + str(lx))
                    return
            else:
                ry = pixel_height_in_column(image, rx, crp_px, ry + 1)
                if ry is None:
                    print(file_name + " couldn't find second matching crop pointer on line x = " + str(rx))
                    return

os.chdir(os.getcwd() + "/RMG_resource")
for file in glob.glob('*.png'):
    if file.startswith("ll"):
        check_fragment(file)
    elif file.startswith("ss"):
        check_fragment(file)
    elif file.startswith("ls"):
        check_fragment(file)

print("fragment test done")

