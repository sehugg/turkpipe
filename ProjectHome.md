Turkpipe allows you to submit batches of jobs to Mechanical Turk using the command line.

## Dependencies ##

  * boto 1.8d
  * python-beautifulsoup
  * python-gdbm

## Outstanding Issues ##

  * Support for boto 1.9b

## Installing turkpipe (instructions for Debian, should work on other `*`nixes) ##
  1. Download & extract boto.
> 2. cd boto && sudo python setup.py install
> 3. sudo apt-get install python-beautifulsoup python-gdbm
> 4. Add the following to ~/.boto:
```
        [Credentials]
        aws_access_key_id="YourAccessKeyID"
        aws_secret_access_key="YourSecretAccessKeyID"

        [Boto]
        debug = 0
        num_retries = 10
```

# Running turkpipe #
> A. `python turkpipe.py`
```
          user@myhost:$ python mturk.py 
          You are in test mode.
          Funds remaining: [$10,000.00]
          There are 0 jobs active. 
```

> B. `python turkpipe.py -l`
```
          user@myhost:$ python mturk.py -l
          You are in LIVE MODE.
          Funds remaining: [$10.14]
          There are 0 jobs active. 
```

> C. `./turkpipe.py -h` and read the online help. Also see
> > http://voxilate.blogspot.com/2009/10/batching-mechanical-turk-jobs-at.html for a quick tutorial.


Do all testing in test mode, not live mode!!