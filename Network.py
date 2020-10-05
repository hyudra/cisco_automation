from netmiko import ConnectHandler
from netmiko.ssh_exception import *
from copy import copy
from module import *
import abc,os

now = getNow()
date = '%s%s%s' %(now["year"],now["month"],now["date"])
time = "%s%s" %(now["hour"],now["minute"])


def initialize(userInput_init,showCmd_init,confCmd_init,reConf_init,writemem_init):
    global userInput
    global showCmd
    global confCmd
    global reConf
    global writemem
    userInput = userInput_init
    showCmd = showCmd_init
    confCmd = confCmd_init
    reConf = reConf_init
    writemem = writemem_init

def getFileName(host,order):
        if userInput['outName'] == 1:
                name = host['ip']
        elif userInput['outName'] == 2:
                name = host['hostname']
        if userInput['isConfMode']:
                folder = 'config_logs'
                extension = '_conf_logs.txt'
        else:
                folder = 'show_logs'
                extension = '.txt'
        logonUser = os.getlogin()
        path = '%s/%s/%s' %(folder,date,logonUser)
        try:
            if not os.path.exists(path):
                os.makedirs(path)
        except:
                pass
        filename = '%s/%s_%s_%s%s' %(path,time,str(order).zfill(2),name,extension)
        filerev = 1
        while True:
                if os.path.isfile(filename):
                        filerev += 1
                        filename = filename[:-4] + '_%s' %(filerev) + filename[-4:]
                else:
                        break
        return filename


class NetworkHost(object):
    logs = ""
    conf_logs = ""
    error = False
    __metaclass__ = abc.ABCMeta
    def Login(self):
            try:
                    state = False
                    self.session = ConnectHandler(**self.host)
                    state = True
                    try:
                            self.getHostname(self.session.find_prompt())
                    except:
                            self.getHostname(self.session.find_prompt(delay_factor=3))
                    if self.host['device_type'] == 'cisco_ios':
                            self.ciscoEnable()
                            self.ciscoExecute()
                    self.session.disconnect()
                    state = False
                    self.logs += 'session completed'
            except ValueError as e:                 #Enable failed or other error
                    if 'Failed to enter enable mode.' in str(e):
                            self.error = True
                            self.logs = 'Failed to enter enable mode -> %s' %(self.host['hostname'])
                            self.session.disconnect()
                    else:
                            self.error = True
                            if state:
                                    self.session.disconnect()
                            self.logs = str(e)
            except AuthenticationException:        #Authen failed
                    self.error = True
                    self.logs = 'Authentication failed -> %s' %(self.host['ip'])
            except (NetMikoTimeoutException,SSHException):        #Timeout
                    self.error = True
                    self.logs = 'Could not open connection to %s' %(self.host['ip'])
            return
#Get hostname after sucessfully login
    def getHostname(self,prompt):
            hostname = prompt
            if self.host['device_type'] == 'cisco_ios':
                    hostname = hostname.replace('>',"")
                    hostname = hostname.replace('#',"")
            self.host.update({'hostname':hostname})
            return


class Cisco(NetworkHost):
    version = ""
    inventory = ""

#Enable Mode for Cisco. Check privilege 15 if in Config mode. Not check if Show mode. (but need to be privileged EXEC mode anyways)
    def ciscoEnable(self):  
        if self.session.check_enable_mode():
                if userInput['isConfMode']:
                        priv = self.session.send_command("show privilege")
                        if priv[len(priv)-2:] != "15":
                                self.session.send_command_timing('disable')
                                ciscoEnable()
        else:
                try:
                        self.session.enable()
                except ValueError as e:
                        raise e
        return

#Main ExecMode Execute commands
    def ciscoExecute(self):
        filename = getFileName(self.host,self.order)
        if (userInput['isConfMode'] and len(confCmd)==0) or (userInput['isConfMode']==False and len(showCmd)==0):
            pass
        elif userInput['isConfMode']==False:  #show mode
                file = open(filename, "w")
                file.write('#####%s#####\n' %(self.host['hostname']))
                file.close
                file = open(filename, "a")
                self.session.send_command('terminal length 0')
                try:
                        self.updateInterface()
                except:
                        self.updateInterface(delay=3)
                for cmd in showCmd:
                        output = self.commandChoice(cmd)
                        file.write('\n<<<<<%s>>>>>>\n' %(cmd))
                        file.write(output)
                file.close()
        elif userInput['isConfMode']:     #config mode
                conf_logs = ""
                if len(confCmd) > 0:
                        conf_logs = self.session.send_config_set(confCmd)
                if len(reConf) > 0:
                        if len(conf_logs) > 0:
                                conf_logs = conf_logs[:conf_logs.rfind(')#end')-1]
                                conf_logs = conf_logs[:conf_logs.rfind(self.host['hostname'])-1]
                        self.session.config_mode()
                        conf_logs += '\n'
                        for cmd in reConf:
                                command_sent = '%s(config)#%s'%(self.host['hostname'],cmd)
                                conf_logs += command_sent + '\n'
                                response = self.session.send_command_timing(cmd)
                                if '[confirm]' in response:
                                        self.session.send_command('')
                        self.session.exit_config_mode()
                        conf_logs += '%s(config)#end\n%s#'%(self.host['hostname'],self.host['hostname'])
                conf_logs = conf_logs[conf_logs.find(self.host['hostname']):]
                self.conf_logs = conf_logs
                file = open(filename, "w")
                file.write(conf_logs)
                file.close()  
                self.logs += 'configured completed\n'
        if writemem:
                response = self.session.send_command_timing('write memory',delay_factor=3)
                wr_logs = 'write memory\n'
                if '[confirm]' in response:
                        response = cleanConfigResponse(response,'write memory')
                        response = self.session.send_command('',delay_factor=3)
                wr_logs += response + '\n%s#' %self.host['hostname']
                file = open(filename, "a")
                file.write(wr_logs)
                file.close()  
                self.logs += 'wrote to memory completed\n'
        return


    
#Use this if want to get custom return information of commnads    
    def commandChoice(self,cmd):
        if validateCmd(cmd, 'show mac address-table'):
                #return self.showMacTable()
                return self.session.send_command(cmd)
        elif validateCmd(cmd, 'show tech-support'):
                return self.session.send_command(cmd,delay_factor=15)
        elif validateCmd(cmd, 'show version'):
                response = self.session.send_command(cmd)
                try:
                    self.version = re.search(r'Cisco IOS Software.*Version\s([^, ]*),?\sRELEASE SOFTWARE',self.session.send_command('show version')).group(1)
                except:
                    pass
                return response
        elif validateCmd(cmd , 'show inventory'):
                response = self.session.send_command(cmd)
                try:
                    for inven in re.finditer(r'PID:\s*([^ ]*)\s*,.*SN:\s*([^ \n]*|^$)\n',response):
                            self.inventory += inven.group(1)
                            if len(inven.group(2))>0:
                                self.inventory += "\t" + inven.group(2) + "\n"
                            else:
                                self.inventory += "\n"
                    self.inventory = self.inventory[:-1]
                except:
                    pass
                return response
        else:
                return self.session.send_command_timing(cmd)

#update Up Interface , Interface List , Abbreviation of each into Hosts Dictionary
    def updateInterface(self,delay = 1):
        output = self.session.send_command('show ip interface brief' , delay_factor=delay)
        list = output.split("\n")
        list = [_f for _f in list if _f]
        topic = list[0].split()
        infindex = topic.index("Interface")
        statusindex = topic.index("Status")
        self.host.update({"inf":[]})
        self.host.update({"infabb":[]})
        self.host.update({"infup":[]})
        self.host.update({"infabbup":[]})
        del list[0]
        for line in list:
                data = line.split()
                statindex = statusindex
                try:
                        i = data.index("administratively")
                        data[i] = "admin"
                except:
                        pass
                try:
                        i = data.index("admin")
                        data[i] = data[i]+ ' ' +data[i+1]
                        statindex = i
                        del data[i+1]
                except:
                        pass
                self.host['inf'].append(data[infindex])
                self.host['infabb'].append(getAbbreviationInf(data[infindex]))
                try:
                    if data[statindex] == 'up':
                            self.host['infup'].append(data[infindex])
                            self.host['infabbup'].append(getAbbreviationInf(data[infindex]))
                except:
                        pass
        return
            
#Add summarize total MAC of each interfaces.
    def showMacTable(self):     #Add summarize total MAC of each interfaces.
        out = self.session.send_command('show mac address-table')
        if 'Invalid input' in out:
                return '\n'
        br = 0
        for i in range(0,len(self.host['infup'])):
                if self.host['infabbup'][i] in out:
                        infchk = copy(self.host['infabbup'])
                        break
                elif self.host['infup'][i] in out:
                        infchk = copy(self.host['infup'])
                        break
                else:
                        br = br + 1
        if br == len(self.host['infup']):
                  return out
        infup = copy(self.host['infup'])
        infchk.append('CPU')
        infup.append('CPU')
        output = "\nCount of UP interface in Mac-Address Table\n"
        for i in range(0,len(infchk)):
                count = sum(1 for _ in re.finditer(r'\b%s\b' % re.escape(infchk[i]), out))
                output += "%s: %s entries\n" %(infup[i],count)
        output += '\n' + out
        return output



