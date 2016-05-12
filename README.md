
# Tsim based Fault Simulator

### Usage

$ python main.py -h

usage: main.py [-h] [--verbose] [-f FAULT_COUNT] [-b BIT_FLIPS] [-s SKIPS]
               [-i ITERATIONS]
               binary

Fault simulator based on tsim-leon3

positional arguments:
  binary                the compiled program to simulate

optional arguments:
  -h, --help            show this help message and exit
  --verbose
  -f FAULT_COUNT, --fault-count FAULT_COUNT
                        number of consecutive faults to inject (default = 1)
  -b BIT_FLIPS, --bit-flips BIT_FLIPS
                        number of random bit flips to inject (default = 1)
  -s SKIPS, --skips SKIPS
                        number of instructions to skip per fault (default = 0)
  -i ITERATIONS, --iterations ITERATIONS
                        iterations to repeat simulation (default = 1)
