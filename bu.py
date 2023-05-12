import utime
import _thread
import math
from collections import deque

from m5stack import *
from m5stack_ui import *
from uiflow import *

import unit

screen = M5Screen()
screen.clean_screen()
screen.set_screen_bg_color(0xFFFFFF)

tof_0 = unit.get(unit.TOF, unit.PORTA)

lab_printm = M5Label("", color=0x00, font=FONT_MONT_18)
# lab_printm = M5Label("", color=0x00, font=FONT_MONT_26)
str_printm = ""

def wrap_text(text):
    n = 40
    new_text = '\n'.join(text[i:i+n] for i in range(0, len(text), n))
    if len(text) % n == 0:
        new_text = new_text.rstrip('\n')
    return new_text


def printa(*args):
    global str_printm
    for ele in args: str_printm += "\n" + str(ele)

def prints():
    global str_printm
    global lab_printm
    text = wrap_text(str_printm)
    lab_printm.set_text(text)
    lab_printm.set_align(ALIGN_IN_BOTTOM_LEFT, ref=screen.obj)
    str_printm = ""

def printm(*args):
    global str_printm
    global lab_printm
    for ele in args: str_printm += str(ele) + " "
    text = wrap_text(str_printm)
    lab_printm.set_text(text)
    lab_printm.set_align(ALIGN_IN_BOTTOM_LEFT, ref=screen.obj)
    str_printm = ""
    
###########################################################

class DQ:
    def __init__(self, size):
        self.dq = deque([])
        self.dq_size = size
        
        self.buf1 = 0
        self.buf2 = 0
        self.sum = 0
        self.mean = 0
        

    def enq(self, val_in):
        if len(self.dq) == self.dq_size:
            self.dq.appendleft(val_in)
            val_out = self.dq.pop()
            self.ref(val_in, val_out)
        else: 
            self.dq.appendleft(val_in)
            self.ref(val_in, 0)
            

    def ref(self, val_in, val_out):
        self.sum += val_in
        self.sum -= val_out
        
        self.mean = self.sum / len(self.dq)
        

class TickDist:
    def __init__(self, itv_sec):
        self.itv_sec = itv_sec
        self.exe_time = None
        
    def is_exc(self, cur_time):
        if self.exe_time is None: self.exe_time = (cur_time // self.itv_sec + 1) * self.itv_sec

        if cur_time < self.exe_time:
            return False
        else: 
            self.exe_time = (cur_time // self.itv_sec + 1) * self.itv_sec
            return True


class LogSit:
    def __init__(self, fname, row, column, date):
        self.fname = fname
        self.row = row
        self.column = column
        try:
            with open(self.fname, 'r') as f:
                self.data = [list(map(int, line.strip().split(','))) for line in f]
                old_date = self.data.pop()[0]
                self.shift_row(date - old_date)
                self.date = date

        except:
            self.data = [[0 for j in range(self.column)] for i in range(self.row)]
            self.date = date
            
            
    def write_csv(self):
        with open(self.fname, 'w') as f:
            for row in self.data:
                f.write(','.join(map(str, row)) + '\n')
            f.write(str(self.date))
            
        ##########dbg
        # with open(self.fname, 'r') as f: printm(f.read())
            


    def shift_row(self, num):
        if num > self.row-1 : num = self.row-1
        for _ in range(num):
            for i in range(self.row):
                if i < self.row-1: self.data[i] = self.data[i+1][:]
                else: 
                    for j in range(self.column): self.data[self.row-1][j] = 0


    def get_today_ratio(self):
        return sum(self.data[self.row-1]) / self.column


class SitItv(TickDist):
    def __init__(self, itv_sec, day_sec, pct_tick, pct_sit):
        super().__init__(itv_sec)
        self.day_sec = day_sec
        self.pct_tick = pct_tick
        self.pct_sit = pct_sit        

        self.ticks = 0
        self.ticks_true = 0

    def process(self, cur_time, log_s):
        if self.is_exc(cur_time):
            j = (cur_time % (self.day_sec)) // self.itv_sec
            if self.ticks_true / max(self.ticks, 1) >= self.pct_sit: log_s.data[log_s.row-1][j] = 1
            log_s.write_csv()
            self.ticks = 0
            self.ticks_true = 0
        else:
            self.ticks += 1
            if is_sitting(self.pct_tick): self.ticks_true += 1


class LogDay:
    def __init__(self, fname, date):
        self.fname = fname
        try:
            with open(self.fname, 'r') as f:
                data = [list(map(int, line.strip().split(','))) for line in f]
                old_date = data.pop()[0]
                self.shift_column(date - old_date)
                self.data = data[0]
                self.date = date

        except:
            self.data = []
            self.date = date

        printa(self.data)
        printa(self.date)
        prints()


    def shift_column(self, num):
        for _ in range(num): self.data.append(0.0)
            
            
    def write_csv(self):
        with open(self.fname, 'w') as f:
            f.write(','.join(map(str, self.data)) + '\n' + str(self.date))

        # with open(self.fname, 'r') as f: printm(f.read())
            

class DayItv(TickDist):
    def __init__(self, itv_sec):
        super().__init__(itv_sec)

    def process(self, cur_time, log_d, log_s):
        if self.is_exc(cur_time):
            log_d.data.append(log_s.get_today_ratio())
            log_d.write_csv()
            log_d.date += 1
            log_s.shift_row(1)
            log_s.date += 1

        
color_hex = -1
def set_bgcolor(color):
    global color_hex
    if color_hex != color:
        screen.set_screen_bg_color(color)
        color_hex = color


lab_c = M5Label(None, color=0x00, font=FONT_MONT_48)
def disp_process(result):
    if result:
        out_val = "(*^^)v"
        set_bgcolor(0x999999)
    else:
        out_val = "(-_-)zzz"
        set_bgcolor(0x999999)

    out_val = str(out_val)
    lab_c.set_text(out_val)
    lab_c.set_align(ALIGN_CENTER, ref=screen.obj)


dq = DQ(size=20)
def is_sitting(pct_tick):
    sens_in = tof_0.distance
    ind = math.log(max(abs(sens_in - 2*dq.buf1 + dq.buf2), 1) / max(sens_in, 1)) + 2.5
    judge = ind < 0  and  200 < sens_in and sens_in < 5000
    dq.enq(judge)
    dq.buf2 = dq.buf1
    dq.buf1 = sens_in
    
    result = dq.mean >= pct_tick
    
    disp_process(result)
    
    return result


day_sec = 15
sit_sec = 3
sit_per_day = int(day_sec/sit_sec)
date = utime.time() // day_sec

log_s = LogSit("log_sit.txt", 3, sit_per_day, date)
log_d = LogDay("log_day.txt", date)
si = SitItv(sit_sec, day_sec, 0.72, 5/300)
di = DayItv(day_sec)
            
def tick_process(cur_time):
    di.process(cur_time, log_d, log_s)
    si.process(cur_time, log_s)
            

def e_button():
    while True:
        cur_time = utime.time()
        tick_process(cur_time)
        if btnA.isPressed(): pass
        if btnB.isPressed(): printm("bbb")
        if btnC.isPressed():
            printm("stop")
            break
_thread.start_new_thread(e_button, ())



# start = time.ticks_us()
# printm(time.ticks_us() - start)


# なんかログファイル周りのバグあった
# うまく

