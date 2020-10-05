from module import *
from queue import Queue
from threading import Thread,Lock
from Network import Cisco,initialize
from copy import copy
import time,inflect

order = inflect.engine()
userInput = {'outName':0,'isConfMode':False,'batch' : True}
WELCOME = 'Welcome to Cisco Automations Beta! Please input information in CONF.xlsx'
MENU1 = ['Please choose your prefer output name: \n 0. Exit Program\n 1. IP address \n 2. Hostname' , 2]
MENU2 = ['Please choose Method: \n 0. Back to last menu\n 1. Execute Show Commands\n 2. Execute Configuration Commands (Batch)\n 3. Execute Configuration Commands (One by One)',3]
now = getNow()
date = '%s%s%s' %(now["year"],now["month"],now["date"])
times = "%s%s" %(now["hour"],now["minute"])
showCmd = None
confCmd = None
reConf = None
global_logs = ''
inputhosts = []
kill = False
conti = True
suminven = ''
sumversion = ''
sequence = 1

class Session(Cisco):
        def __init__(self,host,hostorder):
                self.host = host
                self.order = hostorder

def sessionWorker(session_q):
        while True:
                global sequence
                host = host_q.get()
                hostorder = host.pop('hostorder',None)
                session = Session(host,hostorder)
                session.Login()
                while True:
                        if session.order == sequence:
                                lock.acquire()
                                sequence += 1
                                break
                        else:
                                time.sleep(0.5)
                session_q.put(session)
                lock.release()
                host_q.task_done()
                if (userInput['batch'] == False and userInput['isConfMode']) and not host_q.empty():
                        global conti
                        global kill
                        conti = False
                        time.sleep(1)
                        ans = input('\nContinue? [Confirm]/exit:')
                        if (ans.lower() in 'exit' and len(ans)>0):
                                host_q.queue.clear()
                                host_q.task_done()
                                kill = True
                                return
                        else:
                                conti = True
                                kill = False
        return

def printWorker():
        while True:
                session = session_q.get()
                global global_logs
                logs = ''
                session_order = order.ordinal(session.order)
                multi_line = False
                if '\n' in session.logs:
                        multi_line = True
                if session.error:
                        logs += '%s: %s --> '%(session_order,session.host['ip'])
                elif multi_line:
                        logs +=  '<<<%s: %s:%s>>>'%(session_order,session.host['hostname'],session.host['ip']) + '\n'
                else:
                        logs += '%s: %s:%s --> '%(session_order,session.host['hostname'],session.host['ip'])
                if (userInput['batch'] == False and userInput['isConfMode']):
                        logs += 'Configured Logs:\n' + session.conf_logs + '\n\n'
                logs += session.logs
                print(logs)
                if multi_line:
                        logs += '\n'
                        print('')
                global_logs += logs + '\n'
                if len(session.inventory)>0:
                        global suminven
                        suminven += '%s:\n%s\n\n' %(session.host['hostname'],session.inventory)
                if len(session.version)>0:
                        global sumversion
                        sumversion += '%s\t%s\n' %(session.host['hostname'],session.version)
                session_q.task_done()
                if (userInput['batch'] == False and userInput['isConfMode']):
                        time.sleep(1.5)
                        while not conti:
                                if kill:
                                        global_logs += '\n...Terminated Program due to User Requested'
                                        return
                                time.sleep(1)
        return

def createFolder():
        if userInput['isConfMode']:
                folder = 'config_logs'
        else:
                folder = 'show_logs'
        logonUser = os.getlogin()
        path = '%s/%s/%s' %(folder,date,logonUser)
        if not os.path.exists(path):
                os.makedirs(path)       
        return path

def getLogs():
        path = createFolder()
        inputInfo = ''
        for host in inputhosts:
                inputInfo += '%s:\ttype=%s\tTarget=%s:%s\tUsername=%s\n' %(order.ordinal(host['hostorder']),host['device_type'],host['ip'],host['port'],host['username'])
        inputInfo = inputInfo[:-1]
        inputInfo_filename = '%s/%s_InputInfo.txt' %(path,times)
        logs_filename = '%s/%s_logs.txt' %(path,times)
        filerev = 1
        while True:
                if os.path.isfile(inputInfo_filename):
                        filerev += 1
                        inputInfo_filename = inputInfo_filename[:-4] + '_%s' %(filerev) + inputInfo_filename[-4:]
                else:
                        break
        filerev = 1
        while True:
                if os.path.isfile(logs_filename):
                        filerev += 1
                        logs_filename = logs_filename[:-4] + '_%s' %(filerev) + logs_filename[-4:]
                else:
                        break
        file = open(inputInfo_filename, "w")
        file.write(inputInfo)
        file.close()
        file = open(logs_filename, "w")
        file.write(global_logs)
        file.close() 
        return

def getData(data,filename):
        path = createFolder()
        filename = '%s/%s_%s.txt' %(path,times,filename)
        filerev = 1
        while True:
                if os.path.isfile(filename):
                        filerev += 1
                        filename = filename[:-4] + '_%s' %(filerev) + filename[-4:]
                else:
                        break
        file = open(filename, "w")
        file.write(data)
        file.close()
        return



#Loop until get accepted input
def getUserInput(MENU):
        while True:
                
                print(MENU[0])
                try:
                        choose = int(eval(input('Method: ')))
                        if choose in range(0,MENU[1]+1):
                                print('\n')
                                return choose
                        else:
                                print('invalid input!\n')   
                except:
                        print('invalid input\n')
                        continue
                


def firstInput():       #Just get name of output
        userInput['outName'] = getUserInput(MENU1)
        if userInput['outName'] ==0:
                sys.exit()
                return
        secondInput()
        return

def secondInput():      #Show mode or Config mode.
        while True:
                x = getUserInput(MENU2)
                if x==0:
                        secondInput()
                        return
                elif x==1:                      #Show Mode
                        try:
                                global showCmd
                                showCmd = pullShowCmd()
                                if len(showCmd) == 0:
                                        print('No commands. Please update Cisco_Show sheet\n')
                                        continue
                                print('\nCommands will send to each devices as below')
                                for cmd in showCmd:
                                        print(cmd)
                                print('Total %s commands\n' %(len(showCmd)))
                        except:
                                print('Cannot pull data from Cisco_Show or have forbid commands\n')
                                continue
                        ans = input('Do you want to use commands in Cisco_Show? (yes/no):')
                        if ans.lower() in 'yes':
                                print('Start executing programs...\n')
                                return
                        elif ans.lower() in 'no':
                                print('')
                                continue
                        else:
                                print('Invalid input.. Back to last menu...')
                                continue
                elif x>=2:                      #Configuration Mode
                        if x == 3:
                                userInput['batch'] = False
                        try:
                                global confCmd
                                confCmd = pullConfigCmd()
                                if len(confCmd) == 0:
                                        print('No commands. Please update Cisco_Conf sheet\n')
                                        continue
                                print('\nCommands will send to each devices as below')
                                for cmd in confCmd:
                                        print(cmd)
                                print('Total %s commands\n' %(len(confCmd)))
                                filterconfCmd()
                        except:
                                print('Cannot pull data from Cisco_Conf\n')
                                continue
                        ans = input('Do you want to use commands in Cisco_Conf? (yes/no):')
                        if ans.lower() in 'yes' and ans != "":
                                print('Start executing programs...\n')
                                userInput['isConfMode'] = True
                                return
                        elif ans.lower() in 'no' and ans != "":
                                print('')
                                continue
                        else:
                                print('Invalid input.. Back to last menu...')
                                continue
        return

def filterconfCmd():   #Add config that need to [confirm] to reConf and filter whatever left to new_confCmd for fast config mode.
        global confCmd
        global writemem
        global reConf
        r = re.compile('no user.*')
        reConf = list(filter(r.match,confCmd))
        confCmd = [x for x in confCmd if not r.match(x)]
        try:
                if validateCmd(confCmd[-1],'write'):
                        writemem = True
                        del confCmd[-1]
        except:
                pass
        return

#Main Operation
if __name__ == '__main__':
        try:
                print(WELCOME)
                commonPass = getCommonPass()
                commonSecret = getCommonSecret()
                writemem = False
                count = 0
                host_q = Queue()
                session_q = Queue()
                confCmd = []
                firstInput()
                initialize(userInput,showCmd,confCmd,reConf,writemem)
                lock = Lock()
        ### Will use below code for Direct telnet or after chain telnet
                try:
                        hosts = getHosts(commonPass,commonSecret)
                        if len(hosts) == 0:
                                print('No explicable host detected. Terminate Program...')
                                sys.exit()   #move to SystemExit exception
                except SystemExit:
                        time.sleep(3)
                        sys.exit()
        ### Create Thread preparing for doing queue (daemon mean won't care for thread to finish)
                if userInput['batch']:
                        num_worker_threads = min(20,len(hosts))
                else:
                        num_worker_threads = 1
                for i in range(num_worker_threads):
                        t = Thread(target=sessionWorker,args=(session_q,))
                        t.setDaemon(True)
                        t.start()
                for host in hosts:
                        count += 1
                        host.update({'hostorder':count})
                        inputhosts.append(copy(host))
                        if host.pop('error',None):
                                print('%s: unexpected input' %(order.ordinal(count)))
                                continue
                        host_q.put(host)
                print_thread = Thread(target=printWorker)
                print_thread.setDaemon(True)
                print_thread.start()
                host_q.join()
                session_q.join()
                getLogs()
                if len(suminven)>0:
                        getData(suminven[:-2],'inventory')
                if len(sumversion)>0:
                        getData(sumversion[:-1],'version')
                print('\nProgram Completed...')
        except ValueError as e:         #Just in case unexpected happened. print error then pause.
                print(str(e))
        os.system('pause')
