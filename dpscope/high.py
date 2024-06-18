from low import DPScope
from numpy.fft import fft
from multiprocessing.pool import ThreadPool
from tkinter import BooleanVar
from threading import Semaphore

def channels(data):
    return data[0::2], data[1::2]

class Task(object):

    def __init__(self, widget, interval):
        self.widget = widget
        self.interval = interval
        self.timer = None
        self.s = Semaphore()

    def start(self):
        self.s.acquire()
        self.timer = self.widget.after(self.interval, self.start)
        self.s.release()
        self.task()

    def stop(self):
        if self.timer:
            self.s.acquire()
            self.widget.after_cancel(self.timer)
            self.s.release()

class Plotter(object):

    def __init__(self, fig):
        self._scope = None
        self.fig = fig
        self.plt = fig.add_subplot(111)
        self.ch1, self.ch2 = self.plt.plot([], [], [], [])
        self.pool = ThreadPool()

        self.ch1b = BooleanVar()
        self.ch1b.set(True)

        self.ch2b = BooleanVar()
        self.ch2b.set(True)

        self._fft = BooleanVar()
        self._fft.set(False)

        self._xy = BooleanVar()
        self._xy.set(False)

        self._USB_voltage = None

    @property
    def scope(self):
        return self._scope

    @scope.setter
    def scope(self, port):
        self._scope = DPScope(port)

    @property
    def both_channels(self):
        return self.ch1b.get() and self.ch2b.get()

    @property
    def xy(self):
        return self._xy.get()

    @property
    def fft(self):
        return self._fft.get()
    
    @property
    def USB_voltage(self):
        if not self._USB_voltage:
            self.scope.adcon_from(0)
            self.scope.set_dac(0, 3000)
            self.scope.set_dac(1, 3000)
            real_dac = sum(self.scope.measure_offset()) / 2
            self.scope.set_dac(0, 0)
            self.scope.set_dac(1, 0)
            nominal_dac = 3 * (1023 / 5.)
            self._USB_voltage = 5. * (nominal_dac / real_dac)

        return self._USB_voltage

    def to_volt(self, adc, gain=1, pregain=1):
        multiplier = (self.USB_voltage/5.) * (20./256) * pregain * gain
        return adc * multiplier

    def read_volt(self):
        return map(self.to_volt, self.scope.read_adc())

    def poll(self):
        self.arm()
        self.plot(*self.parse(self.read()))
        self.scope.abort()
        
    def read(self, nofb=205):
        data = None
        while not data:
            data = self.scope.read_back(nofb)

        return data[1:] # need first byte?

    def parse(self, data):
        ch1 = data
        ch2 = []
        if self.both_channels:
            ch1, ch2 = channels(data)

        if self.fft:
            ch1 = fft(ch1)
            ch2 = fft(ch2)

        if self.xy:
            return ch1, ch2, [], []
        else:
            return [], ch1, [], ch2

    def reader(self, nofb=205):
       while True:
           yield self.read(nofb)

    def arm(self):
        if self.both_channels:
            self.scope.arm(0)
        else:
            self.scope.arm_fft(0, self.ch1b.get() or self.ch2b.get()*2)

    def plot(self, x1=[], y1=[], x2=[], y2=[]):
        if len(y1) and not len(x1):
            x1 = range(len(y1))

        if len(y2) and not len(x2):
            x2 = range(len(y2))

        self.ch1.set_data(x1, y1)
        self.ch2.set_data(x2, y2)

        self.plt.relim()
        self.plt.autoscale_view()
        self.fig.canvas.draw()


