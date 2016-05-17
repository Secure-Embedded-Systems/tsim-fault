
# Tsim based Fault Simulator

### Usage
```bash
$ python main.py -h
usage: main.py [-h] [--verbose] [-f FAULT_COUNT] [-b BIT_FLIPS] [-s SKIPS]
               [-i ITERATIONS] [-d DATA] [-1 START] [-2 END]
               binary correct-output

Fault simulator based on tsim-leon3

positional arguments:
  binary                the compiled program to simulate
  correct-output        the correct output to expect from program

optional arguments:
  -h, --help            show this help message and exit
  --verbose
  -f FAULT_COUNT, --fault-count FAULT_COUNT
                        number of consecutive faults to inject (default = 1)
  -b BIT_FLIPS, --bit-flips BIT_FLIPS
                        number of random bit flips to inject (if -d == 0)
                        (default = 1)
  -s SKIPS, --skips SKIPS
                        number of instructions to skip per fault (default = 0)
  -i ITERATIONS, --iterations ITERATIONS
                        iterations to repeat simulation (default = 1)
  -d DATA, --data DATA  data to XOR for induced fault error (0 means random
                        bit) (default = 0)
  -1 START, --start START
                        starting address or label to inclusively start
                        injecting faults (default = main)
  -2 END, --end END     ending address or label to exclusively end injecting
                        faults (default = 0x40001964)

Copy and paste reports to a spreedsheet program.
```



#### known issues
* there is a subtle race condition between reading tsim output and tsim actually outputing that
causes an exception.  just restart it.

