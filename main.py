#!/usr/bin/python
import sys,os
import subprocess, thread, threading, pty, select, signal
import re, random
import argparse

class Watchdog:
    def __init__(self, timeout, userHandler=None):  # timeout in seconds
        self.timeout = timeout
        #self.handler = userHandler if userHandler is not None else self.defaultHandler
        #self.timer = threading.Timer(self.timeout, self.handler)
        #self.timer.start()
        signal.signal(signal.SIGALRM, self.defaultHandler)
        signal.alarm(self.timeout)

    def reset(self):
        #self.timer.cancel()
        #self.timer = threading.Timer(self.timeout, self.handler)
        signal.alarm(self.timeout)

    def stop(self):
        signal.alarm(0)

    def defaultHandler(self,n,n2):
        sys.stderr.write('WATCHDOG\n')
        raise self

class Tsim():
    
    def __init__(self, progname):
        self.progname = progname
        self.q = select.poll()
        self.load_tsim()
        self.done = False
        self.lpc = 0
        self.output_regex = re.compile('{(.*?)}',flags=re.DOTALL)
        

    def load_tsim(self,):
        master, slave = pty.openpty()
        self.master = master
        self.slave = slave

        #os.close(master)
        #os.close(slave)

        #master, slave = pty.openpty()

        self.tsim = subprocess.Popen(['tsim-leon3',self.progname], stdin=subprocess.PIPE, stdout=slave, close_fds=True)
        self.stdout = os.fdopen(master)
        self.q.register(self.stdout, select.POLLIN)
        self.read(20)


    def kill(self,):
 
       #[os.close(x) for x in self.fds]
        #self.tsim.terminate()
        self.tsim.communicate()
        #self.tsim.kill()
        #self.tsim.wait()
        #del self.master
        #del self.slave
        #self.tsim.stdout
        #os.close(self.tsim.stdin)
        #self.q.unregister(self.stdout)
        #self.stdout.close()
        #os.close(self.master)
        os.close(self.slave)



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
            #print '<',l
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
        rf = None
        i =0 
        while rf is None:
            rf=self.read(17)
            i += 1
            if i > 5:
                raise IOError('register file is none')

        #rf = rf.splitlines()

        if 'LOCALS' in rf[2]:
            rf = rf[1:]
        regs = rf[2:2+8]
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
        #while True:
            #try:
        l = self.read(1)[0]
        #print 'substring on : ', l
        bp_num = int(l[10:l.index('at')-1])
        self.write('run\n')
        self.read(2)
        self.write('del '+str(bp_num)+'\n')
        #self.reset()
        #pass
        self.step()

    def step(self,):
        self.write('step\n')
        l = self.read(1)

        if l is None:
            return '','',''

        if len(l[0]) < 3:
            l = self.read(1)
            if l is None: 
                return '','',''

        while True:
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
                    sys.stderr.write('Program finished')
                    self.done = True
                else:
                    print ('unknown string: '+l)



    def cont(self,):
        self.write('cont\n')

    def check_output(self,):
        out = ''

        i = 0
        self.write('reset\n')
        self.write('bt\n')
        l = self.read(1)

        if l is not None:
            out += l[0]

        while 'Program exited normally.' not in out:
            i += 1
            if 'IU in error mode' in out:
                self.match = 'IU in error mode'
                return 3
            elif i > 1000:
                raise IOError('read returning None')
            else:
                # this is a hack
                self.write('reset\n')
                self.write('bt\n')

                l = self.read(1)
                if l:
                    out += l[0]


        match = ''
        try:
        #print 'output:',out, 'len:',len(out)
            match = self.output_regex.search(out).group(1)
        except:
            print 'out: ',out
            match = self.output_regex.search(out).group(1)
            
        #self.match = '(no output)'
        #return 2
        #raise RuntimeError('No {} tag found in output: '+out)

        self.match = match

        if match == self.correct_output:
            return 0
        return 1

    def get_registers(self,s):
        regs = []
        num = s.count('%')
        for _ in range(0,num):
            i = s.index('%')
            if s[i+1] in 'gilo': 
                regs.append(s[i+1:i+3])
                s = s[i+2:]
            elif s[i+1:i+3] in ['fp','sp']:
                # frame pointer is i6
                regs.append('i6')
                s = s[i+3:]
            elif s[i+1:i+4] in ['psr','wim','tbr']:
                regs.append(s[i+1:i+4])
                s = s[i+4:]
            elif s[i+1:i+3] == 'hi':
                pass
            else:
                print hex(self.pc), hex(self.npc)
                raise ValueError('invalid register: ' + s)

        return regs



                
    def reset(self,):
        self.kill()
        self.load_tsim()
        self.lpc = 0


    def resolve_label(self, label):
        try:
            return int(label)
        except:
            self.write('break '+label + '\n')
            l = self.read(1)[0]
            self.log(l)
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
        self.data_error = kwargs.get('data_error',0)
        self.verbose = kwargs.get('verbose',False)


        self.report = []
        self.coverage = 0
        self.num_faulty = 0
        self.num_correct = 0
        self.iteration = 0

    def add_record(self, iteration, instr_num, output, faulty, ftype, addr, instru, reg_affected, origval, faultyval):
        """
            ftype:
                0: correct output
                1: incorrect output
                2: no output
                3: processor crashed
        """
        useful = 0
        if ftype == 1:
            useful = 1

        self.report.append([iteration, instr_num, output, faulty, ftype, addr, instru, reg_affected, origval, faultyval, useful])

    def produce_report(self,):
        print 'num_faults\tnum_skips\tnum_bits\tcoverage\tinstructions in range'
        print '\t'.join([str(self.num_faults),str(self.num_skips),str(self.num_bits),
                str(self.num_correct * 1.0 / (self.num_correct+self.num_faulty)),
                str(self.range_count)])
        print 'iteration\tinstrution #\toutput\tvalid\ttype\tPC\tinstruction\tregister affected\toriginal value\tfaulty value\tuseful'
        for i in self.report:
            print '\t'.join([str(x) for x in i])


    def set_range(self, func_or_addr_start, func_or_addr_end):
        self.set_start(func_or_addr_start)
        self.set_end(func_or_addr_end)

    def set_start(self, func_or_addr):
        self.start = func_or_addr

    def set_end(self, func_or_addr):
        self.end = self.resolve_label(func_or_addr)

    def set_correct_output(self,out):
        self.correct_output = out

    def get_error(self, val):
        fval = val
        if self.data_error == 0:
            for j in range(0,self.num_bits):
                ra = random.randint(0,31)
                fval = fval ^ (1<<ra)
            return fval
        else:
            return (val ^ self.data_error)


    def attack(self,):
        timeout_timer = Watchdog(1)
        atEndOfRange = False
        i = 0
        while not atEndOfRange:
            regi = i
            instri = i
            regs = []
            last_regs = []
            instr = 1
            ftype = 0
            faults = self.num_faults
            self.run_until(self.start)
            self.range_count = 0
            while True:
                try:
                    last_regs = regs[:]
                    last_faults = faults
                    last_regi = regi
                    last_instr = instr
                    last_instri = instri
                    while self.lpc != self.end and faults > 0:
                        timeout_timer.reset()
                        self.range_count += 1
                        (addr, opcode, args) = self.step()
                        self.log(str(addr)+" "+str(opcode) +" "+args)
                        faulted_instruction = ''
                        faulted_pc = 0

                        register_affected = -1
                        origval = 0
                        faultval = 0
                        self.refresh_regs()

                        # put fault stuff here
                        if self.num_skips and instr > instri:
                            npc = self.read_reg('npc')
                            for j in range(1,self.num_skips):
                                npc += 4
                            self.write_reg('pc',npc)
                            faults -= 1
                            faulted_instruction = self.pc_instr
                            faulted_pc = self.pc
                            self.log(self.pc +' '+ self.pc_instr +' '+"(skipped +"+str(self.num_skips-1)+')')
                            self.log('pc -> '+' '+ str(npc))

                        new_regs = self.get_registers(args)
                        regs += new_regs

                        if self.num_bits and len(regs) > regi:
                            val = self.read_reg(regs[regi])
                            
                            # inject a bit flip
                            fval = self.get_error(val)
                            self.write_reg(regs[regi], fval)
                            faulted_instruction = opcode+' '+args
                            faulted_pc = addr

                            self.log('%s: %s -> %s' % (regs[regi], hex(val), hex(fval)))
                            self.refresh_regs()

                            register_affected = -(len(regs)-len(new_regs) - regi)
                            origval = val
                            faultval = fval

                            regi += 1
                            faults -= 1

                        instr += 1
                    self.cont()
                    ftype = self.check_output()
                    timeout_timer.reset()
                    break
                except (Watchdog) as e:
                    self.log('timer burned out')
                    timeout_timer.reset()
                    self.reset()
                    self.run_until(self.start)
                    wdt = False
                    regs = last_regs[:]
                    instr = last_instr
                    regi = last_regi
                    faults = last_faults
                    instri = last_instri
            
            timeout_timer.stop()
            correct = 1
            if ftype == 0:
                self.num_correct += 1
                self.log('output is correct (%s)' % self.match)
                self.log('')
            else:
                correct = 0
                self.num_faulty += 1
                self.log('output is incorrect (%s)' % self.match)
                self.log('')
            self.add_record(self.iteration, i, self.match, correct, ftype, faulted_pc, faulted_instruction,
                            register_affected, origval, faultval)
            i += 1
            atEndOfRange = (self.lpc == self.end)

            while True:
                try:
                    timeout_timer.reset()
                    self.reset()
                    break
                except Watchdog:
                    print 'reset hanged'


        self.iteration += 1
        timeout_timer.stop()

    def log(self, s):
        if self.verbose:
            sys.stderr.write(str(s)+'\n')


def run(start, end, num_faults, num_bits, num_skips, iterations, err, verbose, binary, correct):

    argv = sys.argv


    fi = FaultInjector(binary, num_faults=num_faults, num_bits=num_bits, num_skips=num_skips,
                        data_error=err, verbose=verbose)

    fi.set_correct_output(correct)
    fi.set_range(start, end)

    for j in range(0,iterations): fi.attack()

    fi.produce_report()




if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Fault simulator based on tsim-leon3', epilog="""
    Copy and paste reports to a spreedsheet program.

    known issues:
        there is a subtle race condition between reading tsim output and tsim actually outputing that
        causes an exception.  just restart it.
    """)
    parser.add_argument('binary', help="the compiled program to simulate")
    parser.add_argument('correct-output', help="the correct output to expect from program")
    parser.add_argument('--verbose', action='store_true')
    parser.add_argument('-f', '--fault-count', help='number of consecutive faults to inject (default = %d)' % 1, type=int, default=1)
    parser.add_argument('-b', '--bit-flips', help='number of random bit flips to inject (if -d == 0) (default = %d)' % 1, type=int, default=1)
    parser.add_argument('-s', '--skips', help='number of instructions to skip per fault (default = %d)' % 0, type=int, default=0)
    parser.add_argument('-i', '--iterations', help='iterations to repeat simulation (default = %d)' % 1, type=int, default=1)
    parser.add_argument('-d', '--data', help='data to XOR for induced fault error (0 means random bit) (default = %d)' % 0, type=int, default=0)
    parser.add_argument('-1', '--start', help='starting address or label to inclusively start injecting faults (default = %s)' % 'main', type=str, default='main')
    parser.add_argument('-2', '--end', help='ending address or label to exclusively end injecting faults (default = %s)' % '0x40001964', type=str, default='0x40001964')
    args = parser.parse_args()
    run(args.start, args.end, args.fault_count, args.bit_flips, args.skips, args.iterations, args.data, args.verbose, 
            args.binary, getattr(args,'correct-output'))









