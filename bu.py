import utime
import time
import _thread
import math
from collections import deque

import wifiCfg
import ntptime

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
    text = text.strip()
    n = 40
    lines = text.split("\n")
    for i in range(len(lines)):
        lines[i] = '\n'.join(lines[i][j:j+n] for j in range(0, len(lines[i]), n))
    new_text = "\n".join(lines)
    return new_text


def printa(*args):
    global str_printm
    str_printm += "\n" + " ".join(map(str, args))

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
    str_printm = " ".join(map(str, args))
    text = wrap_text(str_printm)
    lab_printm.set_text(text)
    lab_printm.set_align(ALIGN_IN_BOTTOM_LEFT, ref=screen.obj)
    str_printm = ""
    
###########################################################


class DQ:
    def __init__(self, size):
        self.dq = deque([])
        self.dq_size = size
        
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
        

class SitJudge(DQ):
    def __init__(self, size):
        super().__init__(size)
        self.buf1 = 0
        self.buf2 = 0

    def is_sitting(self, pct_tick):
        sens_in = tof_0.distance
        ind = math.log(max(abs(sens_in - 2*self.buf1 + self.buf2), 1) / max(sens_in, 1)) + 2.5
        judge = ind < 0  and  200 < sens_in and sens_in < 5000
        self.enq(judge)
        self.buf2 = self.buf1
        self.buf1 = sens_in
        
        result = self.mean >= pct_tick
        
        # disp_process(result)
        
        return result

color_hex = -1
def set_bgcolor(color):
    global color_hex
    if color_hex != color:
        screen.set_screen_bg_color(color)
        color_hex = color

# lab_c = M5Label(None, color=0x00, font=FONT_MONT_48)
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


def ref_rtc(force=False):
    # ssid = "Buffalo-G-2E40"
    # password = "mv6dgb383bx5f"
    ssid = "haselab"
    password = "haselove"
    if not wifiCfg.wlan_sta.isconnected():
        printm("Connecting to Wi-Fi...\nSSID : " + ssid)
        wifiCfg.connect(ssid, password, timeout=10)
        for _ in range(10 * 2):
            time.sleep(0.5)
            if wifiCfg.wlan_sta.isconnected():
                time.sleep(1)
                printm()
                break

    try:
        # ntp = ntptime.client(host='jp.pool.ntp.org', timezone=9 + (-24 * 2))
        ntp = ntptime.client(host='jp.pool.ntp.org', timezone=9)
    except:
        if force: raise Exception('Failed to connect to NTP server.\nCan\'t get time.')
    

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


class LogDay:
    def __init__(self, fname, date):
        self.fname = fname
        try:
            with open(self.fname, 'r') as f:
                lines = f.readlines()
                self.data = [float(x) for x in lines[0].split(',')]
                old_date = int(lines[1])
                self.shift_column(date - old_date)
                self.date = date

        except:
            self.data = []
            self.date = date


    def shift_column(self, num):
        for _ in range(num): self.data.append(0.0)
            
            
    def write_csv(self):
        with open(self.fname, 'w') as f:
            f.write(','.join(map(str, self.data)) + '\n' + str(self.date))

        #############dbg
        # with open(self.fname, 'r') as f: printm(f.read())
            

class SitItv(TickDist):
    def __init__(self, itv_sec, day_sec, sj, pct_tick, pct_sit):
        super().__init__(itv_sec)
        self.day_sec = day_sec
        self.sj = sj
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
            if self.sj.is_sitting(self.pct_tick): self.ticks_true += 1


class DayItv(TickDist):
    def __init__(self, itv_sec):
        super().__init__(itv_sec)

    def process(self, cur_time, log_d, log_s):
        if self.is_exc(cur_time):
            ####################################tmp
            # log_d.data.append(log_s.get_today_ratio())
            # log_d.write_csv()
            log_d.date += 1
            log_s.shift_row(1)
            log_s.date += 1


class TimeRefItv(TickDist):
    def __init__(self, itv_sec):
        super().__init__(itv_sec)

    def process(self, cur_time):
        if self.is_exc(cur_time): ref_rtc(force=False)


################################################
# global variable

ref_rtc(force=True)
sit_sec = 3 
day_sec = 288 * 3 
ref_sec = 4 * 60 * 60

log_lines = 4

sit_per_day = int(day_sec/sit_sec)
date = utime.time() // day_sec

log_s = LogSit("log_sit.txt", log_lines, sit_per_day, date)
log_d = LogDay("log_day.txt", date)
sj = SitJudge(size=20)
si = SitItv(sit_sec, day_sec, sj, 0.72, 5/300)
di = DayItv(day_sec)
tri = TimeRefItv(ref_sec)



labels = []
def clear_disp():
    global labels
    lcd.clear(0x999999)
    for l in labels: l.delete()
    labels = []
    
def initA():
    global labels
    clear_disp()
    labels.append(M5Label(None, color=0x63707a, font=FONT_MONT_22))
    labels.append(M5Label(None, color=0x63707a, font=FONT_MONT_22))
    labels.append(M5Label(None, color=0x3d445c, font=FONT_MONT_48))


def tick_processA():
    global labels
    year, month, day, hour, minute, second, weekday, yearday = utime.localtime()
    disp_date = "%04d/%02d/%02d" % (year, month, day)
    labels[0].set_text(disp_date)
    labels[0].set_align(ALIGN_CENTER, x=-30, y=-20, ref=screen.obj)

    disp_dow = ["Mon.", "Tue.", "Wed.", "Thu.", "Fri.", "Sat.", "Sun."]
    labels[1].set_text(disp_dow[weekday])
    labels[1].set_align(ALIGN_CENTER, x=65, y=-20, ref=screen.obj)
    if weekday == 5: labels[1].set_text_color(0x5753b5)
    elif weekday == 6: labels[1].set_text_color(0xb55353)
    else: labels[1].set_text_color(0x63707a)
    
    disp_time = "%02d:%02d:%02d" % (hour, minute, second)
    labels[2].set_text(disp_time)
    labels[2].set_align(ALIGN_CENTER, y=20, ref=screen.obj)

    # disp_time = "%d:%02d:%02d" % (hour, minute, second)
    # labels[2].set_text(disp_time)
    # labels[2].set_align(ALIGN_CENTER, y=20, ref=screen.obj)



def initB(log_lines):
    global labels
    clear_disp()
    text_st = (16, 15)
    graph_st = (16, text_st[1]+23)
    graph_h = 23
    all_h = 55
    
    for _ in range(log_lines): labels.append(M5Label(None, color=0x63707a, font=FONT_MONT_18))
    for _ in range(log_lines): labels.append(M5Label(None, color=0x63707a, font=FONT_MONT_18))
    
    # printm(sum(sum(log_s.data, [])))
    now = utime.localtime()

    for di, log_day in enumerate(log_s.data):
        ts = utime.mktime(now) - 86400 * (log_lines - di - 1)
        year, month, day, hour, minute, second, weekday, yearday = utime.localtime(ts)

        text_p = (text_st[0], text_st[1]+di*all_h)
        graph_p = (graph_st[0], graph_st[1]+di*all_h)
        disp_dow = ["Mon.", "Tue.", "Wed.", "Thu.", "Fri.", "Sat.", "Sun."]
        text = "%02d/%02d %s" % (month, day, disp_dow[weekday])
        if di == log_lines - 1: text += " (Today)"
        labels[di].set_text(text)
        labels[di].set_pos(text_p[0], text_p[1])
        sit_time_m = sum(log_day) * sit_sec // 60 * 100
        # sit_time_m = sum(log_day) * sit_sec // 60
        text = "%dh%dm" % divmod(sit_time_m, 60)
        labels[di+log_lines].set_text(text)
        labels[di+log_lines].set_align(ALIGN_IN_TOP_RIGHT, x=-16, y=text_p[1], ref=screen.obj)
        if weekday == 5: labels[di].set_text_color(0x5753b5)
        elif weekday == 6: labels[di].set_text_color(0xb55353)
        else: labels[di].set_text_color(0x63707a)

        for li, log in enumerate(log_day):
            if log == 1: color_line = 0x385075
            else: color_line = 0xa5a5a5
            lcd.line(graph_p[0]+li, graph_p[1], graph_p[0]+li, graph_p[1]+graph_h, color_line)

def tick_processB():
    pass


def initC():
    global labels
    clear_disp()

def tick_processC():
    pass
            



def tick_process(cur_time, status):
    if status is None  or  status == "A": tick_processA()
    if status == "B": tick_processB()
    if status == "C": tick_processC()

    di.process(cur_time, log_d, log_s)
    si.process(cur_time, log_s)
    tri.process(cur_time)
            

def main():
    set_bgcolor(0x999999)
    status = None
    initA()
    while True:
        if btnA.isPressed(): 
            if status != "A":
                initA()
                status = "A"
            else: break
        if btnB.isPressed(): 
            # if status != "B":
            initB(log_lines)
            status = "B"
        if btnC.isPressed(): 
            # if status != "C":
            initC()
            status = "C"
        cur_time = utime.time()
        tick_process(cur_time, status)
    printm("main_stop")

main()


# start = time.ticks_us()
# printm(time.ticks_us() - start)


