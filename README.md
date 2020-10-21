# multiplex
View output of multiple processes, in parallel, in the console, with an interactive TUI

## Installation
```shell script
pip install multiplex
# or better yet
pipx install multiplex
```

## Examples

### Parallel Execution Of Commands

```shell script
mp \
    './some-long-running-process.py --zone z1' \
    './some-long-running-process.py --zone z2' \
    './some-long-running-process.py --zone z3'
```

![Par](http://multiplex-static-files.s3-website-us-east-1.amazonaws.com/o.par.gif)

You can achive the same effect using Python API like this:

```python
from multiplex import Multiplex

mp = Multiplex()
for zone in ['z1', 'z2', 'z3']:
    mp.add(f"./some-long-running-process.py --zone {zone}")
mp.run()
```

### Dynamically Add Commands

`my-script.sh`:
```shell script
#!/bin/bash -e
echo Hello There

export REPO='git@github.com:dankilman/multiplex.git'

mp 'git clone $REPO'
mp 'pyenv virtualenv 3.8.5 multiplex-demo && pyenv local multiplex-demo'
cd multiplex
mp 'poetry install'
mp 'pytest tests'

mp @ Goodbye -b 0
```

And then running: 
```shell script
mp ./my-script.sh -b 7
```

![Seq](http://multiplex-static-files.s3-website-us-east-1.amazonaws.com/o.seq.gif)

### Python Controller
An output similar to the first example can be achieved from a single process using
the Python Controller API.

```python
import random
import time
import threading

from multiplex import Multiplex, Controller

CSI = "\033["
RESET = CSI + "0m"
RED = CSI + "31m"
GREEN = CSI + "32m"
BLUE = CSI + "34m"
MAG = CSI + "35m"
CYAN = CSI + "36m"

mp = Multiplex()

controllers = [Controller(f"zone z{i+1}", thread_safe=True) for i in range(3)]

for controller in controllers:
    mp.add(controller)

def run(index, c):
    c.write(
        f"Starting long running process in zone {BLUE}z{index}{RESET}, "
        f"that is not really long for demo purposes\n"
    )
    count1 = count2 = 0
    while True:
        count1 += random.randint(0, 1000)
        count2 += random.randint(0, 1000)
        sleep = random.random() * 3
        time.sleep(sleep)
        c.write(
            f"Processed {RED}{count1}{RESET} orders, "
            f"total amount: {GREEN}${count2}{RESET}, "
            f"Time it took to process this batch: {MAG}{sleep:0.2f}s{RESET}, "
            f"Some more random data: {CYAN}{random.randint(500, 600)}{RESET}\n"
        )

for index, controller in enumerate(controllers):
    thread = threading.Thread(target=run, args=(index+1, controller))
    thread.daemon = True
    thread.start()

mp.run()
```

![Cont](http://multiplex-static-files.s3-website-us-east-1.amazonaws.com/o.cont.gif)

### Help Screen
Type `?` to toggle the help screen.

![help](http://multiplex-static-files.s3-website-us-east-1.amazonaws.com/help.png)
