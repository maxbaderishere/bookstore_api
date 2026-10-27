
def draw_heart(size=12):

    for j in range(int(size * 1.4), -int(size * 1.2) - 1, -1):
        y = j / size
        row = ""
        for i in range(-int(size * 1.5), int(size * 1.5) + 1):
            x = i / size
            if (x**2 + y**2 - 1) ** 3 - x**2 * y**3 <= 0:
                row += "<3"
            else:
                row += "  "
        print(row.rstrip())
 
 
if __name__ == "__main__":
    draw_heart(12)
 