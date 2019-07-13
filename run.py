import lib.config3 as config
config.main()
conf = config.conf
import schedule, logging, sys, time, subprocess, os
import omni
from multiprocessing import Process

logger = logging.getLogger(__name__)

def run_pingrr():
	python3_command = "python2.7 /opt/omni/pingrr.py"  # launch your python2 script using bash
	process = subprocess.Popen(python3_command.split(), stdout=subprocess.PIPE)
	output, error = process.communicate()  # receive output from the python2 script

def short_queue():
	try:
		logger = config.create_logger('short')
		logger.info("Creating Short Queue")
		schedule.every(5).minutes.do(omni.modify_new)
		schedule.every(5).minutes.do(omni.session_search)
		schedule.run_all()
		while True:
			try:
				schedule.run_pending()
				time.sleep(1)
			except:
				pass
	except Exception as e:
		logger.error("Error Running Schedule - %s" % e)
		logger.error('Error on line {}'.format(sys.exc_info()[-1].tb_lineno, type(e).__name__, e))
		pass

def long_queue():
	try:
		logger = config.create_logger('long')
		logger.info("Creating Long Queue")

		schedule.every(2).hours.do(run_pingrr)
		schedule.every(12).hours.do(omni.full_check)
		schedule.run_all()
		while True:
			try:
				schedule.run_pending()
				time.sleep(1)
			except:
				pass
	except Exception as e:
		logger.error("Error Running Schedule - %s" % e)
		logger.error('Error on line {}'.format(sys.exc_info()[-1].tb_lineno, type(e).__name__, e))
		pass


Process(target=short_queue).start()
Process(target=long_queue).start()

#logger = config.create_logger('manual')
#omni.modify_new()
