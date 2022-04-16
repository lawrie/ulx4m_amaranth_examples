def rle(y,x,fn,cells):
    f = open(fn,"r")
    n = 0
    tx = x
    num = False

    def res_n():
        nonlocal n
        nonlocal num
        num = False
        n = 0

    def get_n():
        nonlocal n
        if (not num):
            n = 1

    while True:
        l = f.readline()
        if l[0] == "#":
            continue
        # metadata
        m = l.split(",")
        m0 = m[0].split("=")
        m1 = m[1].strip().split("=")
        w = int(m0[1])
        h = int(m1[1])
        break

    while True:
        c = f.read(1)
        if not c or c == "!":
            break
        elif c == "\n":
            continue
        elif c >= '0' and c <= '9':
            num = True
            n = n * 10 + (ord(c) - ord('0'))
        elif (c == "b"):
            get_n()
            tx += n
            res_n()
        elif (c == "o"):
            get_n()
            for i in range(n):
                cells[y][tx + i] = 1
            tx += n
            res_n()
        elif (c == "$"):
            get_n()
            y += n
            tx = x
            res_n()

    f.close()

