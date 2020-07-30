class BC:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


# Give difference of two lists, sorted. List1: Bigger list
def listdiff(list1, list2):
    diff = (list(set(list1) - set(list2)))
    diff.sort()
    return diff

def print_line_with_mainheader(line):
    print(BC.OKGREEN,"--------------------------------------------------",BC.END)
    print(BC.OKGREEN,BC.BOLD,line,BC.END)
    print(BC.OKGREEN,"--------------------------------------------------",BC.END)

def print_line_with_subheader1(line):
    print(BC.OKBLUE,"--------------------------------------------------",BC.END)
    print(BC.OKBLUE,BC.BOLD,line,BC.END)
    print(BC.OKBLUE,"--------------------------------------------------",BC.END)


def insert_line_into_file(file,string,addedstring):
    with open(file, 'r') as ffr:
        contents = ffr.readlines()
    with open(file, 'w') as ffw:
        for l in contents:
            ffw.write(l)
            if string in l:
                ffw.write(addedstring+'\n')

def blankline():
    print("")

#Is variable an integer
def isint(s):
    try:
        int(s)
        return True
    except ValueError:
        return False

#Read lines of file
def readlinesfile(filename):
  try:
    f=open(filename)
    out=f.readlines()
    f.close()
  except IOError:
    print('File %s does not exist!' % (filename))
    sys.exit(12)
  return out

#Write a string to file simply
def writestringtofile(string,file):
    with open(file, 'w') as f:
        f.write(string)

#Natural (human) sorting of list
def natural_sort(l):
    convert = lambda text: int(text) if text.isdigit() else text.lower()
    alphanum_key = lambda key: [ convert(c) for c in re.split('([0-9]+)', key) ]
    return sorted(l, key = alphanum_key)

# Reverse read function.
def reverse_lines(filename, BUFSIZE=20480):
    #f = open(filename, "r")
    filename.seek(0, 2)
    p = filename.tell()
    remainder = ""
    while True:
        sz = min(BUFSIZE, p)
        p -= sz
        filename.seek(p)
        buf = filename.read(sz) + remainder
        if '\n' not in buf:
            remainder = buf
        else:
            i = buf.index('\n')
            for L in buf[i+1:].split("\n")[::-1]:
                yield L
            remainder = buf[:i]
        if p == 0:
            break
    yield remainder

def clean_number(number):
    return np.real_if_close(number)


#Function to get unique values
def uniq(seq, idfun=None):
   # order preserving
   if idfun is None:
       def idfun(x): return x
   seen = {}
   result = []
   for item in seq:
       marker = idfun(item)
       # in old Python versions:
       # if seen.has_key(marker)
       # but in new ones:
       if marker in seen: continue
       seen[marker] = 1
       result.append(item)
   return result


#Extract column from matrix
def column(matrix, i):
    return [row[i] for row in matrix]

#From Knarr
def printDate():
    import datetime
    dagur = datetime.datetime.now()
    string1 = dagur.strftime('%d.%m.%Y')
    string2 = dagur.strftime('%H:%M')
    print('Time:%s Date:%s' % (string2, string1))
    return None