import io
import logging
from complot.utils import Timer, Lock

#formatter_info = logging.Formatter('%(message)s')
#formatter_debug = logging.Formatter('%(levelname)5s %(module)3s.%(funcName)-10s %(lineno)3s %(message)s')

formatter = logging.Formatter('%(asctime)s  %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

fileHandler = logging.FileHandler("complot.log")

# put log lines in string so we can put it in a window later
errors_list = io.StringIO()
errors_list_handler = logging.StreamHandler(errors_list)
errors_list_handler.setFormatter(formatter)

logger = logging.getLogger('complot')
logger.setLevel(logging.DEBUG)

logger.addHandler(errors_list_handler)
logger.addHandler(fileHandler)

# create global objects
lock = Lock()
timer = Timer()
