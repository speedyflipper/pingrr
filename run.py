import lib.config3 as config
config.main()
conf = config.conf
import schedule, logging, sys, time, subprocess, os
from logging.handlers import RotatingFileHandler
import omni

logger = logging.getLogger(__name__)

logger.info(conf)

formatter = logging.Formatter('%(asctime)s - %(levelname)5s - %(module)15s:%(funcName)30s:%(lineno)5s - %(message)s')
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
consoleHandler = logging.StreamHandler(sys.stdout)
consoleHandler.setFormatter(formatter)
logger.addHandler(consoleHandler)
logging.getLogger("requests").setLevel(logging.WARNING)
logger.setLevel(conf['pingrr']['log_level'])
fileHandler = RotatingFileHandler(os.path.join(os.path.dirname(sys.argv[0]), 'logs', 'omni.log'), maxBytes=1024 * 1024 * 2, backupCount=1)
fileHandler.setFormatter(formatter)
logger.addHandler(fileHandler)

def run_pingrr():
	python3_command = "python2.7 /opt/omni/pingrr.py"  # launch your python2 script using bash
	process = subprocess.Popen(python3_command.split(), stdout=subprocess.PIPE)
	output, error = process.communicate()  # receive output from the python2 script

try:
	logger.info("Creating Omni Queue")

	schedule.every().day.at("2:30").do(run_pingrr)
	schedule.every(3).hours.do(omni.check)
	schedule.run_all()
	while True:
		schedule.run_pending()
		time.sleep(1)

except Exception as e:
	logger.error("Error Running Schedule - %s" % e)
	logger.error('Error on line {}'.format(sys.exc_info()[-1].tb_lineno, type(e).__name__, e))
	pass
