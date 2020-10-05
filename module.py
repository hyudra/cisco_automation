import datetime,os,sys , re
import ipaddress,xlrd
from intspan import intspan
from getpass import getpass

cmd_list = {"configure":['conf#igure'],         #For checking short commands. (e.g. wr , sh run)
            "reload":['relo#ad']
            ,"write":['wr#ite'],
            "show tech-support":['sh#ow','tec#h-support']
            ,"show mac address-table":['sh#ow','mac#','ad#dress-table']
            ,"show version":['sh#ow','ver#sion']
            ,"show inventory":['sh#ow','inven#tory']
            }
forbid_cmd = ["configure","reload","write"]     #Forbid command for show mode.

def getCommonPass():
    print('Please enter common password for each hosts (Leave blank if do not have one)')
    password = getpass('Password: ')
    print('')
    return password

def getCommonSecret():
    print('Please enter common secret for each Cisco hosts (Leave blank if do not have one)')
    secret = getpass('Secret Password: ')
    print('')
    return secret

def groupVlan(vlanlist):        #Grouping vlan  e.g. 2,3,4,7,8,10 -> 2-4,7-8,10
    vlan_merged = str(intspan(vlanlist))
    return vlan_merged

def readExcel(workbook,worksheet,header=True):  #not explicible for protected sheet
    if(header):     #in case need first row as header
        workbook = xlrd.open_workbook(workbook)
        worksheet = workbook.sheet_by_name(worksheet)
        keys = [worksheet.cell(1, col_index).value for col_index in range(worksheet.ncols)]
        data = []
        for row_number in range(2,worksheet.nrows):
            row_data = {}
            for col_number, cell in enumerate(worksheet.row(row_number)):
                try:
                    row_data[keys[col_number]] = int(cell.value)
                except:
                    row_data[keys[col_number]] = cell.value
            data.append(row_data)
    else:       #ignore first row, get only first column
        data = []
        workbook = xlrd.open_workbook(workbook)
        worksheet = workbook.sheet_by_name(worksheet)
        for row_number in range(1,worksheet.nrows):
            row_data = worksheet.cell_value(row_number,0)
            if len(row_data) == 0:
                continue
            data.append(row_data)
    return data

#pull information from hosts.def file
def pullShowCmd():
    '''                      #Old code for pull from text file
    file = open('custom_cmds.def','r')
    text = file.read()
    text = text.replace("\t"," ")
    text = re.sub(' +',' ',text).strip()
    list = text.split('\n')
    list = list[list.index('[Commands List]')+1:list.index('[End]')]
    list = [x.strip() for x in list]
    list = [_f for _f in list if _f]
    '''
    data = readExcel('CONF.xls','Cisco_Show',header=False)
    for cuscmd in data:
        for key in forbid_cmd:
            if validateCmd(cuscmd, key):
                return ValueError('Forbid Commands')
#   file.close()
    return data

def pullConfigCmd():
    data = readExcel('CONF.xls','Cisco_Conf',header=False)
    return data


#validate that Host in target format or not
def validate_Host(record):
    #Check first item is valid IP Address , If cannot will raise Exception
    ipaddress.IPv4Address(record['ip'])
    if record['device_type'] == 'paloalto_panos':       #add more delay for Palo Alto
        record.update({'global_delay_factor':15})
    try:                                                #invalid port will force as default ssh port
        if record['port'] not in list(range(0,65535)):
            record['port'] = '22'
    except:
        record['port'] = '22'
    return

#get Hosts list
def getHosts(commonPass,commonSecret):
    df = readExcel('CONF.xls','Host')
    #Delete Null record
    for i in range(len(df)-1,-1,-1):
        if(len(df[i]['ip']) == 0):
            del df[i]
            continue
        elif(len(df[i]['username']) == 0):
            del df[i]
            continue
        elif(len(df[i]['device_type']) == 0):
            del df[i]
            continue
        elif(len(df[i]['password']) == 0):
            if len(commonPass) == 0:
                del df[i]
                continue
            df[i]['password'] = commonPass
        if(len(df[i]['secret']) == 0):
            df[i]['secret'] = commonSecret
    #Cleaning host list. Add default parameter or update it as error host.
    for record in df:
        try:
            validate_Host(record)
            record.update({"error":False})
        except:
            record.update({"error":True})
            continue
    return df

def partialMatch(entry, full, minimum):
    return len(entry) >= minimum and entry == full[:len(entry)]

def validateCmd(entry, cmd):
    entry = entry.lower()
    entry = entry.split()
    if len(entry) < len(cmd_list[cmd]):
        return False
    for index,word in enumerate(entry):
        if index >= len(cmd_list[cmd]):
            break
        if not partialMatch(word, cmd_list[cmd][index].replace('#',''), cmd_list[cmd][index].find('#')):
            return False
    return True

#get shortname of interface  e.g. GigabitEthernet0/0/1  --> Gi0/0/1
def getAbbreviationInf(text):
        try:
                infnum = re.search('\d+((/\d+)+(\.\d+)?)?',text).group(0)
        except:
                return ValueError()
        infabb = text[0:2]+infnum
        return infabb

# Cleaning response from netmiko.ConnectHandler(**kwarg).send_config_timing
def cleanConfigResponse(response,cmd):
    try:
        if ('#' in response):
            response = response[response.rfind('#')+1:]
            if response[:response.find('\n')] in cmd:
                response = response[response.find(response)+len(response):]
        elif response[:response.find('\n')] in cmd:
            response = response[response.find(response)+len(response):]
    except:
            pass
    return response

#get current time in dictionary form
def getNow():
    now = datetime.datetime.now()
    year = str(now.year).zfill(4)
    month = str(now.month).zfill(2)
    date = str(now.day).zfill(2)
    hour = str(now.hour).zfill(2)
    minute = str(now.minute).zfill(2)
    sec = str(now.second).zfill(2)
    keys = ['year','month','date','hour','minute','sec']
    values = [year,month,date,hour,minute,sec]
    js = dict(list(zip(keys,values)))
    return js

#get path for pyinstaller --onefile. (pyinstaller will create temp file when run with 1 executable file.
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


