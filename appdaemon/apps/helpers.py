# superminor2's helper functions

def brightness_up(brightness):
    # Takes 0 - 100 range and maps it to 0 - 255
    # turn_on service takes 0-255 in brightness=
    normal = round(int(float(brightness)) * 255 / 100)
    return normal