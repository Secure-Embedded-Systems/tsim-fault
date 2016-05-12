#!/bin/python
import sys,os,select
import subprocess, threading, pty
import re, random


class Tsim():
    
    def __init__(self, progname):
        self.progname = progname
        master, slave = pty.openpty()
        self.tsim = subprocess.Popen(['tsim-leon3',progname], stdin=subprocess.PIPE, stdout=slave)
        self.stdout_lock = threading.Lock()
        self.stdout_list = []
        self.stdout = os.fdopen(master)
        self.q = select.poll()
        self.q.register(self.stdout, select.POLLIN)
        self.done = False
        self.correct_output = ''

        self.lpc = 0

        self.start = 'main'
        self.end = 0x40000000

        self.output_regex = re.compile('{(.*)}',flags=re.DOTALL)
        
        self.read(20)

    def read(self,lines):
        s = []
        l = self.q.poll(300)
        #print l
        if not l:
            return None

        for i in range(0,lines):
            l = self.stdout.readline()
            print l[:len(l)-1]
            while l[0] == '#':
                l = self.stdout.readline()
            s.append(l)
        return s

    def write(self, s):
        print '>', s
        self.tsim.stdin.write(s)

    def refresh_regs(self):
        self.write('reg\n')
        # read next 17 lines for register file
        rf=self.read(17)
        #rf = rf.splitlines()

        regs = rf[2:2+7]
        special = rf[11]

        self.iregs = []
        self.lregs = []
        self.oregs = []
        self.gregs = []
        self.sregs = []

        for i in regs:
            self.iregs.append(int(i[7:7+8],16))
            self.lregs.append(int(i[15+3:18+8],16))
            self.oregs.append(int(i[24+3:27+8],16))
            self.gregs.append(int(i[35+3:38+8],16))

        self.sregs.append(int(special[6:6+8],16))
        self.sregs.append(int(special[23:23+8],16))
        self.sregs.append(int(special[39:39+8],16))
        self.sregs.append(int(special[53:53+8],16))

        self.pc = int(rf[13][6:6+8],16)
        self.npc = int(rf[14][6:6+8],16)

        #print 'i:', [hex(x) for x in self.iregs]
        #print 'l:', [hex(x) for x in self.lregs]
        #print 'o:', [hex(x) for x in self.oregs]
        #print 'g:', [hex(x) for x in self.gregs]
        #print 's:', [hex(x) for x in self.sregs]
        #print 'pc: ', hex(self.pc)
        #print 'npc: ', hex(self.npc)

    def read_reg(self, reg):
        c = reg[0]
        if c == 'i':
            return self.iregs[int(reg[1])]
        if c == 'l':
            return self.lregs[int(reg[1])]
        if c == 'o':
            return self.oregs[int(reg[1])]
        if c == 'g':
            return self.gregs[int(reg[1])]

        if reg == 'psr':
            return self.sregs[0]
        if reg == 'wim':
            return self.sregs[1]
        if reg == 'tbr':
            return self.sregs[2]
        if reg == 'y':
            return self.sregs[3]

        if reg == 'pc':
            self.pc
        if reg == 'npc':
            self.npc

        raise ValueError('invalid register: ',reg)

    def write_reg(self, reg, val):
        c = reg[0]
        if c not in 'ilog':
            if reg not in ['psr','wim','tbr','y', 'pc','npc']:
                raise ValueError('invalid register: '+reg)

        self.write('reg '+reg+' '+str(val)+'\n')
        #print self.read(1)[0]

    def run_until(self, func_or_addr):
        func_or_addr = str(func_or_addr)
        self.write('break '+func_or_addr+'\n')
        l = self.read(1)[0]
        print 'substring on : ', l
        bp_num = int(l[10:l.index('at')-1])
        self.write('run\n')
        self.read(1)[0]
        self.read(1)[0]
        self.write('del '+str(bp_num)+'\n')

    def step(self,):
        self.write('step\n')
        l = self.read(1)

        if l is None: 
            return

        if len(l[0]) < 3:
            l = self.read(1)
            if l is None: return

        try:
            l = l[0]
            addr = int(l[11:19+1],16)
            if 'nop' not in l:
                instr = l[31:l.index('\t')]
                args = l[l.index('\t')+1:len(l)-1]
            else:
                instr = 'nop'
                args = ''

            self.lpc = addr

            print hex(addr), instr, args
            return args
        except:
            if 'Program exited normally.' in l:
                print 'Program finished'
                self.done = True
            else:
                raise RuntimeError('unknown string: '+l)

    def set_start(self, func_or_addr):
        self.start = func_or_addr

    def set_end(self, func_or_addr):
        self.end = self.resolve_label(func_or_addr)

    def cont(self,):
        self.write('cont\n')

    def set_correct_output(self,out):
        self.correct_output = out

    def check_output(self,):
        out = ''
        l = self.read(1)
        i = 0
        extra = 0
        while 'Program exited normally.' not in out:
            i += 1
            if l is not None:
                out += l[0]
                l = self.read(1)
            if 'IU in error mode' in out:
                return False
            if i > 20:
                self.write('bt\n')
                extra =2

        if extra: self.read(extra)

        match = ''
        try:
            match = self.output_regex.search(out).group(1)
        except:
            raise RuntimeError('No {} tag found in output: '+out)

        self.match = match

        if match == self.correct_output:
            return True
        return False

    def get_registers(self,s):
        regs = []
        num = s.count('%')
        for _ in range(0,num):
            i = s.index('%')
            if s[i+1] in 'gilo': 
                regs.append(s[i+1:i+3])
                s = s[i+2:]
            elif s[i+1:i+3] == 'fp':
                # frame pointer is i6
                regs.append('i6')
                s = s[i+3:]
            elif s[i+1:i+4] in ['psr','wim','tbr']:
                regs.append(s[i+1:i+4])
                s = s[i+4:]
            else:
                raise ValueError('invalid register: ' + s)

        return regs



                

    def attack(self,):
        iterations = 20

        for i in range(0, iterations):
            regi = i
            regs = []
            faults = 1
            self.run_until(self.start)
            while self.lpc != self.end and faults > 0:
                args = self.step()
                self.refresh_regs()

                # put fault stuff here
                
                regs += self.get_registers(args)

                if len(regs) > regi:
                    val = self.read_reg(regs[regi])
                    
                    # inject a bit flip
                    ra = random.randint(0,31)
                    val ^= (1<<ra)
                    self.write_reg(regs[regi], val)

                    regi += 1
                    faults -= 1



            self.cont()

            if self.check_output():
                print 'output is correct (%s)' % self.match
            else:
                print 'output is incorrect (%s)' % self.match

            self.reset()

    def reset(self,):
        self.write('reset\n')
        while self.read(1) != None: pass


    def set_range(self, func_or_addr_start, func_or_addr_end):
        self.set_start(func_or_addr_start)
        self.set_end(func_or_addr_end)

    def resolve_label(self, label):
        try:
            return int(label)
        except:
            self.write('break '+label + '\n')
            l = self.read(1)[0]
            print l
            bp_num = int(l[10:l.index('at')-1])
            addr = int(l[l.index(':')-8:l.index(':')],16)
            self.write('del '+str(bp_num)+'\n')
            return addr



def run():
    argv = sys.argv
    if len(argv) < 2:
        sys.stderr.write('usage: %s <binary> <fault-file>\n' % argv[0])
        sys.exit(1)

    tsim = Tsim(argv[1])
    tsim.set_correct_output('ans = 6')
    tsim.set_range('main', 0x40001944)

    tsim.attack()




if __name__ == '__main__':
    run()
