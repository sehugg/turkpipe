# turkpipe
Turkpipe allows you to submit batches of jobs to Mechanical Turk using the command line.

*** USE AT YOUR OWN RISK!!! THIS TOOL MAY SPEND YOUR MONEY!!! ***

Dependencies

    python-boto
    python-beautifulsoup
    python-gdbm 

Installing turkpipe (instructions for Debian, should work on other *nixes)

1. sudo apt-get install python-beautifulsoup python-gdbm python-boto
  
2. Add the following to ~/.boto:

        [Credentials]
        aws_access_key_id="YourAccessKeyID"
        aws_secret_access_key="YourSecretAccessKeyID"
        
        [Boto]
        debug = 0
        num_retries = 10

Running turkpipe

        user@myhost:$ ./turkpipe.py 
        You are in test mode.
        Funds remaining: [$10,000.00]
        There are 0 jobs active. 

        user@myhost:$ ./turkpipe.py -l
        You are in LIVE MODE.
        Funds remaining: [$10.14]
        There are 0 jobs active. 

        ./turkpipe.py -h and read the online help.

Also see http://voxilate.blogspot.com/2009/10/batching-mechanical-turk-jobs-at.html for a quick tutorial. 

*REMEMBER: Do all testing in test mode, not live mode!!*
