#!/usr/bin/python

"""
Copyright (c) 2009-2010 Voxilate, Inc.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""

from boto.mturk.connection import *
from boto.mturk.question import *
from boto.mturk.price import *
from boto.mturk.qualification import *
from boto.s3 import *
from boto.s3.connection import *
from os.path import *
import sys,getopt,re,cPickle,urllib,string,time,os,uuid,mimetypes,codecs
import gdbm
from BeautifulSoup import BeautifulSoup,Tag
from xml.sax.saxutils import escape
import platform

def getNodeName():
  """
  >>> type(getNodeName())
  <type 'str'>
  """
  name = platform.node()
  if not name:
    name = socket.gethostname()
    if not name:
      name = os.environ.get('COMPUTERNAME')
  assert(name)
  return name

# create a default bucket name based on hostname
bucketname = 'turkpipe_%s' % getNodeName().replace('.','_')

# redirect stdout
real_stdout = codecs.getwriter('utf8')(sys.stdout)
sys.stdout = sys.stderr

frame_height = 1000
testmode = True
title = None
description = None

s3conn = S3Connection()
# Bucket try/except contributed by idm 6/22/2010
try:
  bucket = s3conn.get_bucket(bucketname)
except boto.exception.S3ResponseError:
  print "The S3 bucket '%s' has been created." % (bucketname)
  bucket = s3conn.create_bucket(bucketname)

SUBMIT_JS = """<script type="text/javascript" language="JavaScript"><!--

// Given the ID of the assignmentId form field element, populate it
// with the assignmentId parameter from the URL.  If no assignment ID
// is present, inform the worker that the HIT is being previewed.
function populateAssignmentID(field_id) {
  var assignment_id_field = document.getElementById(field_id);
  var paramstr = window.location.search.substring(1);
  var parampairs = paramstr.split("&");
  for (i in parampairs) {
    var pair = parampairs[i].split("=");
    if (pair[0] == "assignmentId") {
      if (pair[1] == "ASSIGNMENT_ID_NOT_AVAILABLE") {
        return null;
      } else {
        assignment_id_field.value = pair[1];
        return pair[1];
      }
    }
  }
  return null;
}
 
function verifyTurkSubmit(field_id)
{
  var assignment_id_field = document.getElementById(field_id);
  if (assignment_id_field.value == '')
  {
    alert("You must accept this HIT to work on it and submit results.");
    return false;
  } else
    return true;
}

// --></script>"""

###

def usage():
  print 'Usage: \n' + sys.argv[0] + ' -j <# jobs> -t "<jobtitle>" -D "<job description>" -o <output> -w <wait seconds> filename.ext filename.ext'
  print """
   -h, --help             Print this help
   -l, --live             Send HITs to live Mturk site (if not specified, 
                          use sandbox)
   -j, --jobs=            Specifies the number of concurrent jobs to send 
                          for each file.
   -o, --output=          Specifies the output file for returned results. 
                          Default is stdout.
   -p, --price=           Specifies the amount to pay per HIT. Default 
                          is .01 USD.
   -t, --title=           Title to post for HITs.
   -D, --description=     Description (instructions) to post for HITs.
   -k, --keywords=        Keywords to use, separated by spaces.
   -d, --duration=        Number of seconds workers have to complete 
                          the HIT.
   -e, --expiration=      Number of seconds before expiring unaccepted 
                          HITs. Default is 300 seconds.
   -A, --approve          Approve all HITs automatically as they're completed.
   -a, --autoapprove=     Automatically approve HITs after the specified 
                          number of seconds. Default is 86400.
   -w, --wait=            Wait the specified number of seconds for the
                          specified HITs to be completed.
   -X, --panic            Cancel all outstanding HITs.
   """  
   
def safefn(fn):
  #return md5.new(fn).hexdigest()
  # TODO: strip off firs char if "C:"?
  return fn[1:]
  
def unpickle(s):
  return cPickle.loads(s)

def pickle(o):
  return cPickle.dumps(o,2)

def uploadfile(fn, data=None):
  key = Key(bucket,safefn(fn))
  if data:
    key.path = fn # for content type  
    key.set_contents_from_string(data, policy='public-read')
  else:
    key.set_contents_from_filename(fn, policy='public-read')
  url = key.generate_url(86400, force_http=True, query_auth=False).replace(':443','')
  print 'Uploaded to',url
  return url

def makeHTMLQuestion(fn, htmldata):
  soup = BeautifulSoup(htmldata)
  #add JS
  soup.find('body')['onload'] = "populateAssignmentID('myAssignmentId')"
  soup.find('head').insert(0, SUBMIT_JS)
  #replace forms
  forms = soup.findAll('form')
  if forms:
    for form in forms:
      if not form.has_key('method'):
        form['method'] = 'POST'
      if not form.has_key('action'):
        if testmode:
          form['action'] = 'http://workersandbox.mturk.com/mturk/externalSubmit'
        else:
          form['action'] = 'http://www.mturk.com/mturk/externalSubmit'
      if not form.has_key('onSubmit'):
        form['onSubmit'] = "return verifyTurkSubmit('myAssignmentId');"
      inputtag = Tag(soup,'input')
      inputtag['type'] = 'hidden'
      inputtag['name'] = 'assignmentId'
      inputtag['id'] = 'myAssignmentId'
      inputtag['value'] = ''
      form.insert(0, inputtag)
  mainurl = uploadfile(fn, str(soup))
  for sub in soup.findAll('img'):
    # TODO
    fn = dirname(fn) + '/' + sub['src']
    uploadfile(fn)
  return ExternalQuestion(escape(mainurl), frame_height)
  
def makeSimpleQuestion(fn):
  text = open(fn,'r').read()
  qn_content = QuestionContent()
  qn_content.append_field('Title',title)
  qn_content.append_field('Text',description + "\n\n" + text)
  qn = Question(content=qn_content, identifier=fn,
                answer_spec=AnswerSpecification(FreeTextAnswer()))
  return QuestionForm([qn])
  
def makeBinaryContentQuestion(fn,ctype):
  ct = ctype.split('/')
  if ct[0] in ('image','video','audio'):
    bin = uploadfile(fn)
    qn_content = QuestionContent()
    qn_content.append_field('Title',title)
    qn_content.append_field('Text',description)
    qn_content.append(Binary(ct[0], ct[1], bin, title))
    qn = Question(content=qn_content, identifier=fn,
                  answer_spec=AnswerSpecification(FreeTextAnswer()))
    return QuestionForm([qn])
  else:
    return None
  
  
def getQuestionForFile(fn):
  root,ext = splitext(fn)
  if ext in ('.html','.htm'):
    return makeHTMLQuestion(fn, open(fn,'r').read())
  else:
    content_type = mimetypes.guess_type(fn)
    #print '%s is %s' % (fn,str(content_type))
    q = None
    if content_type and content_type[0]:
      q = makeBinaryContentQuestion(fn,content_type[0])
    if not q:
      q = makeSimpleQuestion(fn)
    return q

class Job:
  def __init__(self, key):
    self.key = key
    self.hitid = None
    self.nassignments = 0
    self.url = None
    self.uploads = []

def makeKeywords(s):
  return list( set(re.findall(r'[A-Za-z]{6,}',s)) )

def parseDuration(s):
  return int(s)
  
##

if __name__=='__main__':

  try:
    opts, args = getopt.getopt(sys.argv[1:],
      "hlj:o:p:t:D:k:e:a:w:XAd:P",
      ["help", "live", "jobs=", "output=", "price=", "title=", "description=", "keywords=", "panic", "test", "expiration=", "autoapprove=", "wait=", "approve", "duration=", "partial"]) 
  except getopt.GetoptError:
    usage()
    sys.exit(2)

  infiles = []
  outfile = None
  nassignments = 1
  price = Price(0.01)
  keywords = None
  panic = 0
  expiration = 300
  duration = 300
  autoApprove = 86400
  timeout = 0
  sleepinterval = 15
  approve = None
  approvalPercentage = 80
  turkmessage = "Thanks!"
  partial = False

  for opt,arg in opts:
    if opt in ('-h','--help'):
      usage()
      sys.exit(2)
    elif opt in ('--test',):
      import doctest
      sys.exit(doctest.testmod(verbose=True))
    elif opt in ('-o','--output'):
      outfile = arg
    elif opt in ('-j','--jobs'):
      nassignments = int(arg)
    elif opt in ('-l','--live'):
      testmode = False
    elif opt in ('-p','--price'):
      price = Price(float(arg))
    elif opt in ('-t','--title'):
      title = arg
    elif opt in ('-D','--description'):
      description = arg
    elif opt in ('-k','--keywords'):
      keywords = string.split(arg)
    elif opt in ('-e','--expiration'):
      expiration = parseDuration(arg)
    elif opt in ('-a','--autoapprove'):
      autoApprove = parseDuration(arg)
    elif opt in ('-d','--duration'):
      duration = parseDuration(arg)
    elif opt in ('-w','--wait'):
      timeout = parseDuration(arg)
    elif opt in ('-X','--panic'):
      panic += 1
    elif opt in ('-A','--approve'):
      approve = True
    elif opt in ('-P','--partial'):
      partial = True
  infiles.extend([abspath(fn) for fn in args])

  qualifications = Qualifications()
  if not testmode:
    qualifications.add(PercentAssignmentsApprovedRequirement('GreaterThan', approvalPercentage))

  if testmode:
    print "You are in test mode."
    jobsfn = expanduser('~/.turkpipe.sandbox.jobs')
  else:
    print "You are in LIVE MODE."
    jobsfn = expanduser('~/.turkpipe.live.jobs')
    
  jobs = None
  def opendb(ro=False):
    global jobs
    while jobs == None:
      try:
        if ro and exists(jobsfn):
          jobs = gdbm.open(jobsfn,'r')
        else:
          jobs = gdbm.open(jobsfn,'cs')
      except gdbm.error:
        time.sleep(1)
    
  def closedb():
    global jobs
    if jobs:
      jobs.close()
      jobs = None
    
  # connect to turk      
  if testmode:
    conn = MTurkConnection(host='mechanicalturk.sandbox.amazonaws.com')
  else:
    conn = MTurkConnection()
  
  # PANIC!
  if panic:
    print "PANIC" + string.join(["!"]*panic,'')
    opendb()
    n = 0
    # iterate through all known jobs, and reject
    key = jobs.firstkey()
    while key:
      job = unpickle(jobs[key])
      n += 1
      print "Cancelling HIT",job.hitid
      conn.disable_hit(job.hitid)
      conn.dispose_hit(job.hitid)
      if panic>=2:
        rs = conn.get_assignments(job.hitid)
        for ass in rs:
          conn.reject_assignment(ass.AssignmentId, "Sorry, I panicked.")
          print "Rejected assignment",ass.AssignmentId
      oldkey = key
      key = jobs.nextkey(key)
      del jobs[oldkey]
    # if -XX, iterate through all HITs that aren't in the list
    if panic>=2:
      for hit in conn.search_hits(page_size=100):
        n += 1
        print "Disabling HIT",hit.HITId
        # disable
        conn.disable_hit(hit.HITId)
        conn.dispose_hit(hit.HITId)
        # reject?
        if panic>=2:
          rs = conn.get_assignments(hit.HITId)
          for ass in rs:
            conn.reject_assignment(ass.AssignmentId, "Sorry, I panicked.")
            print "Rejected assignment",ass.AssignmentId
        try:
          del jobs[hit.RequesterAnnotation]
        except KeyError:
          print "-- was not in database"
    if n==0:
      print "Huh, there was nothing to panic about."
    elif panic<2:
      print "Run with -XX to super-panic and reject *all* HITs."
    closedb()
    sys.exit(0)

  # if no input files, show some info
  if len(infiles)==0:
    opendb(True)
    print 'Funds remaining:',conn.get_account_balance()
    print 'There are',len(jobs),'jobs active.'
    key = jobs.firstkey()
    while key:
      job = unpickle(jobs[key])
      print job.hitid+'\t'+job.key
      key = jobs.nextkey(key)
    sys.exit(3)
    
  # create HITs
  opendb()
  for fn in infiles:
    key = fn
    if not jobs.has_key(key):
      if not exists(key):
        print "%s: No file was found." % key
        sys.exit(2)
      else:
        job = Job(key)
        if not title:
          print "To create a HIT, you really should have a title (-t)."
          sys.exit(1)
        if not description:
          print "To create a HIT, you really should have a description (-D)."
          sys.exit(1)
        #if not keywords:
        #  keywords = makeKeywords(title + " " + description)

        question = getQuestionForFile(key)
        rs = conn.create_hit(
          question=question,
          title=title,
          description=description,
          keywords=keywords,
          reward=price,
          max_assignments=nassignments,
          annotation=key,
          duration=duration,
          qualifications=qualifications
          )
        for hit in rs:
          # TODO: if not created properly?
          if not hasattr(hit,'HITId'):
            print "%s: Could not create HIT." % key
            sys.exit(5)
          print '%s: Created HIT %s.' % (key,hit.HITId)
          job.hitid = hit.HITId
          job.nassignments = nassignments
        # TODO: http://code.google.com/p/boto/issues/detail?id=275
        jobs[key] = pickle(job)
  closedb()
    
  # check on status of previously created HITs
  time0 = time.time()
  done = False
  while not done:
    # parse input files, create jobs if necc
    completedHits = []
    for fn in infiles:
      # get lock
      opendb()
      key = fn
      job = unpickle(jobs[key])
      ## extend hit?
      if nassignments > job.nassignments:
        conn.extend_hit(job.hitid,
          assignments_increment=nassignments-job.nassignments,
          expiration_increment=None)
        job.nassignments = nassignments
        jobs[job.key] = pickle(job)
      ## return assignments?
      rs = conn.get_assignments(hit_id=job.hitid)
      hit = conn.get_hit(hit_id=job.hitid)
      hit = hit[0]
      hitstatus = hit.HITStatus
      print '%s: %d/%d assignments completed.' % (job.key, len(rs), job.nassignments)
      if len(rs) >= job.nassignments: # TODO: or (hitstatus == 'Unassignable' and partial):
        completedHits.append((hit,rs))
      # give up lock
      closedb()
      
    # completed?
    if len(completedHits) == len(infiles):
      break
    
    # result == 0 when we are successful
    td = timeout - (time.time() - time0)
    if td < 0:
      result = 1
      if timeout > 0:
        print 'Timed out.'
      else:
        print 'Use -w <timeout> to wait for this assignment to complete.'
      break
    else:
      time.sleep(min(sleepinterval, td))

  # successful if all assignments completed
  if outfile:
    real_stdout = codecs.getwriter('utf8')(open(outfile,'w'))
  if len(completedHits) == len(infiles):
    opendb()
    for hit,rs in completedHits:
      key = hit.RequesterAnnotation
      # print assignments
      for ass in rs:
        for a in ass.answers:
          for b in a:
            i = 0
            # TODO: unicode
            for k,v in b.fields:
              if i>0:
                real_stdout.write(',')
              i += 1
              real_stdout.write(unicode(v))
            real_stdout.write('\n')
      # approve assignments?
      if approve:
        for ass in rs:
          conn.approve_assignment(ass.AssignmentId,turkmessage)
        # remove it from our DB
        del jobs[key]
        print '%s: All assignments approved.' % key
    closedb()

  # flush jobs and exit
  real_stdout.close()
  sys.exit(0)

