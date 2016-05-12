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

        self.lpc = 0
        self.output_regex = re.compile('{(.*)}',flags=re.DOTALL)
        
        self.read(20)

    def read(self,lines):
        s = []
        l = self.q.poll(1)
        #print l
        if not l:
            l = self.q.poll(2)
            if not l:
                return None

        for i in range(0,lines):
            l = self.stdout.readline()
            #print l[:len(l)-1]
            while l[0] == '#':
                l = self.stdout.readline()
            s.append(l)
        return s

    def write(self, s):
        #print '>', s
        self.tsim.stdin.write(s)

    def refresh_regs(self):
        self.write('reg\n')
        # read next 17 lines for register file
        rf=self.read(17)
        #rf = rf.splitlines()

        if 'LOCALS' in rf[2]:
            rf = rf[1:]
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
            self.oregs.append(int(i[29:29+8],16))
            self.gregs.append(int(i[40:40+8],16))

        self.sregs.append(int(special[6:6+8],16))
        self.sregs.append(int(special[22:22+8],16))
        self.sregs.append(int(special[38:38+8],16))
        self.sregs.append(int(special[52:52+8],16))

        self.pc = int(rf[13][6:6+8],16)
        self.npc = int(rf[14][6:6+8],16)
        self.pc_instr = rf[13][26:len(rf[13])-2]
        self.npc_instr = rf[14][26:len(rf[14])-2]

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
            return self.pc
        if reg == 'npc':
            return self.npc

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
        #print 'substring on : ', l
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
                args = l[l.index('\t')+1:len(l)-2]
            else:
                instr = 'nop'
                args = ''

            self.lpc = addr

            return addr, instr, args
        except:
            if 'Program exited normally.' in l:
                print 'Program finished'
                self.done = True
            else:
                raise RuntimeError('unknown string: '+l)
    def cont(self,):
        self.write('cont\n')
    def check_output(self,):
        out = ''
        l = self.read(1)
        i = 0
        while 'Program exited normally.' not in out:
            i += 1
            if l is not None:
                out += l[0]
                l = self.read(1)
            if 'IU in error mode' in out:
                self.match = 'IU in error mode'
                return False
            if i > 20:
                break


        match = ''
        try:
            match = self.output_regex.search(out).group(1)
        except:
            match = '(no output)'
            #raise RuntimeError('No {} tag found in output: '+out)

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



                
    def reset(self,):
        self.write('reset\n')
        self.write('bt\n')
        l = self.read(1)
        while l != None and '%pc          %sp' not in l[0]:
            l = self.read(1)
        #self.lpc = 0


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


class FaultInjector(Tsim):
    def __init__(self,progname, **kwargs):
        Tsim.__init__(self,progname)
        self.start = 'main'
        self.end = 0x40000000
        self.correct_output = ''

        self.num_faults = kwargs.get('num_faults',1)
        self.num_bits = kwargs.get('num_bits',1)
        self.num_skips = kwargs.get('num_skips',0)


    def set_range(self, func_or_addr_start, func_or_addr_end):
        self.set_start(func_or_addr_start)
        self.set_end(func_or_addr_end)

    def set_start(self, func_or_addr):
        self.start = func_or_addr

    def set_end(self, func_or_addr):
        self.end = self.resolve_label(func_or_addr)

    def set_correct_output(self,out):
        self.correct_output = out



    def attack(self,):
        iterations = 20

        for i in range(0, iterations):
            regi = i
            instri = i
            regs = []
            instr = 1
            faults = self.num_faults
            self.run_until(self.start)
            while self.lpc != self.end and faults > 0:
                (addr, opcode, args) = self.step()
                print addr,opcode,args
                self.refresh_regs()

                # put fault stuff here
                if self.num_skips and instr > instri:
                    npc = self.read_reg('npc')
                    for i in range(1,self.num_skips):
                        npc += 4
                    self.write_reg('pc',npc)
                    faults -= 1
                    print self.pc, self.pc_instr, "(skipped +"+str(self.num_skips-1)+')'
                    print 'pc -> ', npc


                regs += self.get_registers(args)

                if self.num_bits and len(regs) > regi:
                    val = self.read_reg(regs[regi])
                    
                    # inject a bit flip
                    fval = val
                    for j in range(0,self.num_bits):
                        ra = random.randint(0,31)
                        fval = val ^ (1<<ra)
                    self.write_reg(regs[regi], fval)

                    print '%s: %s -> %s' % (regs[regi], hex(val), hex(fval))
                    self.refresh_regs()

                    regi += 1
                    faults -= 1

                instr += 1

            self.cont()

            if self.check_output():
                print 'output is correct (%s)' % self.match
                print
            else:
                print 'output is incorrect (%s)' % self.match
                print

            self.reset()



def run():
    argv = sys.argv
    if len(argv) < 2:
        sys.stderr.write('usage: %s <binary> <fault-file>\n' % argv[0])
        sys.exit(1)

    fi = FaultInjector(argv[1], num_bits=0, num_skips=2)
    fi.set_correct_output('ans = 6')
    fi.set_range('main', 0x40001944)

    fi.attack()




if __name__ == '__main__':
    run()
