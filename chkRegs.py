#!/usr/bin/env python
'''
Created on Oct 21, 2015

@author: leblancr

This is UNPUBLISHED PROPRIETARY SOURCE CODE of Broadcom Corporation;
the contents of this file may not be disclosed to third parties, copied
or duplicated in any form, in whole or in part, without the prior
written permission of Broadcom Corporation.

Copyright here All Rights Reserved
Broadcom confidential
'''

__version__ = "$Revision: 589837 $".strip('$ ').split(': ')[1]

import baseTest
import collections
import datetime
import itertools
import multiprocessing
import os
import re
import shutil
import SPCL_lib
import sr
import subprocess
import sys
import telnetlib
import tempfile
import thread
import threading
import time 
import traceback
from Lib import glLib
from Lib import iperf2
from Lib  import paramikoe

import inspect
def where_am_i():
    (frame, filename, line_number, function_name, lines, index) = inspect.getouterframes(inspect.currentframe())[1]
    return "***** %s %s in %s" % (filename, line_number, function_name)

class myThread (threading.Thread):
    def __init__(self, threadID, name, method_to_run):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = name
        self.method_to_run = method_to_run
    def run(self):
        print "Starting " + self.name
        self.method_to_run()

class chkRegs_c(baseTest.spclTest_c):
    """ Staple does:
        1. makes instance of the class.
        2. Adds the station variable (not available in __init__()).
        3. Calls the class __init__().
        4. Calls the class testRun().
    """

    def __init__(self, **kwargs):
        ''' Check SVN revisions, read config file. '''
        path_sep = {'Linux': '/', 'Windows': '\\', 'win32': '\\'}
        # **kwargs is staple's command line arguments from <test_script>.txt.
        self.kwargs = kwargs
        
        print "Command line options: "
        for k, v in self.kwargs.iteritems():
            print "%s: %s" % (k, v)                
                
        self.config = self.station.config1 # Assign config dictionary to new name.


        # temp
        if 0:
            filename = '../../43452_register_names/43452_register_names.txt'
            with open(filename, 'r') as f:
                print 'Opening {}:'.format(filename)
                for line in f.readlines():
                    if line.startswith('x'):
                        print line
            sys.exit()        

        if 0:
            filename = '../../43452_register_names/wlc_phyreg_ac.h'
            with open(filename, 'r') as f:
                print 'Opening {}:'.format(filename)
                for line in f.readlines():
                    if len(line.split()) == 3:
                        if line.split()[2].startswith('0x'):
                            print '{} {}'.format(int(line.split()[2], 16), line.split()[1][:-5])
#                    if line.startswith('x'):
#                        print line
            sys.exit()        

        if 0:
            filename = '../../43452_register_names/43452_phyreg_register_names.txt'
            with open(filename, 'r') as f:
                print 'Opening {}:'.format(filename)
                for line in f.readlines():
                    print '\'{}\': \'{}\','.format(line.split()[0], line.split()[1])
#                    if line.startswith('x'):
#                    print line
#            sys.exit()        





#        for k in self.config:
#            print "k: %s" % k
#            print "self.config[k]: %s" % self.config[k]

#        try:
        self.desired_svn_ref_rev = self.config['MISCELLANEOUS']['svn_ref_rev']
        self.verbosity = self.kwargs['verbosity']
        
        # Convert string to bool.
        if self.config['MISCELLANEOUS']['associate'] == 'True': # Associate or not for compare and test operation
            self.associate = True
        elif self.config['MISCELLANEOUS']['associate'] == 'False':
            self.associate = False
        else:
            print 'Error getting config value.'
            sys.exit()
            
        self.ap_os = self.config['MISCELLANEOUS']['ap_os']
        self.ap_ip = self.config['MISCELLANEOUS']['ap_ip']
        self.ap_type = self.config['MISCELLANEOUS']['ap_type'] # hard or soft
        self.branch = self.config['MISCELLANEOUS']['branch']
        self.chanspecs = self.config['CHANNELS']['channels'] # Make to list.
        if type(self.chanspecs) == str:
            self.chanspecs = [self.chanspecs]
        self.chip_num = ''
        self.chip_rev = ''
        self.compare_performed = False
        self.CONTROLLER = self.station.CONTROLLER
        self.data = {'ref': {}, 'chip': {}}
        self.desired_svn_ref_rev = self.config['MISCELLANEOUS']['svn_ref_rev']
        self.dhd_prefix = '' 
        self.DUT = self.station.DUT[0]
        self.dut_wired_intf = self.config['DUTS']['0']['dut_wired_intf']
        self.dut_wl_ip = self.config['DUTS']['0']['intf']['0']['ip']
        self.global_loops = self.config['MISCELLANEOUS']['global_loops']
        self.ifconfig = {}
        self.ignore_list = {'phyreg': {}, 'radioreg': {}, 'phytable': {}}
        self.iperf_server_ip = self.config['MISCELLANEOUS']['iperf_server_ip']
        self.iperf_server_os = self.config['MISCELLANEOUS']['iperf_server_os']            
        self.max_page = {'phyreg': 3, 'radioreg': 0, 'phytable': 71}
        self.mismatch_info = {}
        self.mode = self.config['MISCELLANEOUS']['mode'] # NIC or dongle
        self.operation = self.kwargs['operation']
#        self.operation_info = {} # Holds info about the operation.
        self.operation_info = {self.operation: {}} 
        self.os_path_sep = os.sep   
        self.phy_rev = ''
        self.pm_mode = '0'
        self.program = self.config['MISCELLANEOUS']['program']
        self.REF = self.station.REF[0]
        self.ref_dir = self.config['MISCELLANEOUS']['ref_dir']
        if self.ref_dir[-1:] != self.os_path_sep:
            self.ref_dir += self.os_path_sep 
#        print self.ref_dir
#            self.script_os_path_sep = sys.platform# System the script is running on.   
#            print self.script_os_path_sep  
#            sys.exit()    
        self.reg_names = {}
        self.reg_sets = {}
        self.SSID = {'soft': {'a': self.config['MISCELLANEOUS']['ssid_soft'], # Both same for soft AP.
                              'b': self.config['MISCELLANEOUS']['ssid_soft'],
                              },
                     'hard': {'a': self.config['MISCELLANEOUS']['ssid_hard_a'], # 5G hard AP SSID
                              'b': self.config['MISCELLANEOUS']['ssid_hard_b'], # 2G hard AP SSID
                              },
                     }
        
        self.spclLib = SPCL_lib.SPCL_lib_c()
        self.start_time = datetime.datetime.now()
        self.run_time = str(self.start_time).split('.')[0].replace(' ', '_')
        self.svn_ref_repository = "http://svn.sj.broadcom.com/svn/wlansvn/groups/dvt/reg_table_diff/"
        self.svn_script_repository = "http://svn.sj.broadcom.com/svn/wlansvn/groups/dvt/chk_regs/"
        self.total_test_loops = 0
        self.unassociated = True
        self.wldir = self.config['FIRMWARE']['wldir']
        self.wlfw = self.config['FIRMWARE']['wlfw']
        self.wlnv = self.config['FIRMWARE']['wlnv']
        self.wlclm = self.config['FIRMWARE']['wlclm']
        self.wl_prefix = '' 
        self.wl_intf = ''
        self.wl_ver = ''
#        except:
#            print "Unexpected error in __init__():", sys.exc_info()[0]
#            raise
        
        # Get DUT operating system type.
        cmd = 'uname -s'
        print "Issue %s to %s" % (cmd, self.DUT.addr)
        ret, output = self.DUT.issuecmd(cmd) 
        
        if ret:
            print "ret: %s" % ret
#            return
            raise TypeError
        else:
            self.dut_os = output.strip()   
            print 'DUT OS: ' + self.dut_os 
            self.dut_os_path_sep = path_sep[self.dut_os]
            print 'DUT OS path separator: ' + self.dut_os_path_sep 
            
        if self.operation not in ['dump', 'compare', 'test', 'loadfw']:
            print "%s is not a valid operation, -h for help." % self.operation
#            raise
            sys.exit()
                    
        if self.wldir[-1:] != self.dut_os_path_sep:
            self.wldir += self.dut_os_path_sep
               
        # Get DUT wired IP address from ifconfig output.
        cmd = 'ifconfig -a'
        ret, output = self.DUT.issuecmd(cmd) # Linux and Mac, doesn't work on Windows.
        if ret:
            print "ret: %s" % ret
#            return
            raise
        lines = output.splitlines()
        
        # Parse ifconfig output.
        for line in lines:      
            if line.strip(): # Skip blank lines.
                tokens = line.split() # Split line into tokens.
                if tokens[0].endswith(':'): 
                    interface = tokens[0][:-1] # Strip off colon.
                    self.ifconfig[interface] = {} # Top level dictionary keys, eth0, eth1 etc..
                    continue # Get following lines after interface line.
                if tokens[0] == 'inet':
                    self.ifconfig[interface]['inet'] = tokens[1] # IP address for that interface.
                   
        self.dut_ip = self.ifconfig[self.dut_wired_intf]['inet']
        
        print "Driver location: %s" % self.wldir
        print "DUT OS: %s" % self.dut_os
        print "DUT IP: %s" % self.dut_ip
        print "DUT WL IP: %s" % self.dut_wl_ip
        print "Access Point OS: %s" % self.ap_os
        print "Access Point type: %s" % self.ap_type
        print "Access Point IP: %s" % self.ap_ip
        print "iPerf server IP: %s" % self.iperf_server_ip

        if self.operation == 'loadfw':
            if self.load_driver():
                print 'Error installing driver'
                return
            if self.get_wl_interface():
                print 'Wireless interface not found.'
                return
            else:
                if self.load_firmware():
                    print 'Error loading firmware'
                    return
                                
            return
        else:
            # If operation is not load firmware must be dump, compare or test.
            self.pmu_names = {'0x620': 'pmu_dependency', 
                              '0x650': 'pmu_control', 
                              '0x658': 'vreg_control', 
                              '0x660': 'pll_control', 
                              '0xc40': 'gci_control',
                              }
            
            # firmware already loaded, look for wireless interface.
            try:
                if self.get_wl_interface():
                    print 'Wireless interface not found, load driver?'
                    sys.exit() 

                # If wireless interface found change to the firmware directory on the DUT.
                cmd = "cd %s" % self.wldir
                ret, output = self.DUT.issuecmd(cmd)
                if ret:
                    print "ret: %s" % ret
                    return None
                
                cmd = 'ver'
                ret, output = self.DUT.issuecmd(cmd, cmdtype='WL')
                if ret:
                    print ret
                    return None
                
                self.wl_ver = output
#                print self.wl_ver                

                if 'adapter not found' in output:
                    print 'Wireless adapter not found, load firmware?'
                    sys.exit()
            except (IndexError) as e:
                print 'Wireless interface not found, load driver?'
                sys.exit()
            
            print ' '
            if self.get_chip_info(): # Can't do if firmware not loaded
                print 'Check firmware loaded.'
                sys.exit()
    
            # Use the register sets in the config file.
            reg_sets = self.config['MISCELLANEOUS']['reg_sets']
            if type(reg_sets) == str:
                reg_sets = [reg_sets] # Make to list.
                
            # Check for valid register set.
            print 'Operating on these register sets:'
            for reg_set in reg_sets:
                print reg_set
                if reg_set not in ['phyreg', 'radioreg', 'phytable', 'pciephyreg', 'pmureg']:
                    print "Unsupported register set: %s" % reg_set
                    print 'Must be one of: phyreg, radioreg, phytable, pciephyreg or pmureg'
                    sys.exit(1)
                else:
                    self.reg_sets[reg_set] = {} # Make dictionary for each register set to store info.
                
            # Read test info from config file.
            try:
                if self.operation in ['test']:
                    # Make a dictionary with info for each test/chanspec/global loops completed/ local loops completed.
                    # ex. self.['test1']['1/20'][1][1]['status']['Fail']
                    #                                 ['comment': 'Failed to associate.']
                    #                                 ['rtcwake_time': 5]
                    for testname in [testname for testname in sorted(self.config['TEST_LOOPS']) if self.config['TEST_LOOPS'][testname] != '0']:
    #                    print "testname: %s" % testname
                        self.operation_info[self.operation][testname] = {}
                        for chanspec in self.chanspecs:
    #                        print "chanspec: %s" % chanspec
                            self.operation_info[self.operation][testname][chanspec] = {}
                            for gloop in range(int(self.global_loops)):
                                gloop += 1 # range() starts at 0.
    #                            print "gloop: %s" % gloop
                                self.operation_info[self.operation][testname][chanspec][gloop] ={}
                                for loop in range(int(self.config['TEST_LOOPS'][testname])): # Tests with 0 loops won't get in here.
                                    loop += 1 # range() starts at 0.
                                    self.operation_info[self.operation][testname][chanspec][gloop][loop] = {'completed': False, 'comment': '', 'status': 'N/A'}
    
                                    # Get rtcwake times if their test loops aren't 0.
                                    for rtc_testname in self.config['RTCWAKE']:
                                        if rtc_testname in self.operation_info[self.operation]:
                                            self.operation_info[self.operation][testname][chanspec][gloop][loop]['rtcwake_time'] = self.config['RTCWAKE'][rtc_testname]
            except ValueError as e:
                print e
                print 'Error in config file.'
                sys.exit()
            
            print 'Tests loops to run:'
            for testname in sorted(self.operation_info[self.operation]):
                test_loops = self.config['TEST_LOOPS'][testname]
                print '{} {} '.format(testname, test_loops)
                self.total_test_loops += int(test_loops)

            self.pmu_names = {'0x620': 'pmu_dependency', 
                              '0x650': 'pmu_control', 
                              '0x658': 'vreg_control', 
                              '0x660': 'pll_control', 
                              '0xc40': 'gci_control',
                              }
            
            print ' '
            print "Running %s on these chanspecs:\n" % self.operation
            print self.chanspecs            
                
            setup_cmds = [self.wl_prefix + 'down',
                          self.wl_prefix + 'ap 0',
                          self.wl_prefix + 'mpc 0',
                          self.wl_prefix + 'up',
                          self.wl_prefix + 'PM 2',
                          self.wl_prefix + 'disassoc',
                          ]
    
            # Set up device
            if self.verbosity > 0:
                print 'Setting up device'
                
            cmd = ';'.join(setup_cmds)
            ret, output = self.DUT.issuecmd(cmd)
            if ret:
                print ret
                return
    
    def associate_ap(self, SSID):
        ''' Issue wl commands to associate with access point.        
        
            Join AP 
            Wl down
            Wl ap 0
            Wl mpc 0
            Wl up
            Wl isup
            (return 1)
            Wl ap
            (return 0)
            Wl disassoc
            Wl join <SSID>
            Sleep 2
            Wl status         
            
            wl status output line:
            Mode: Managed    RSSI: -47 dBm    SNR: 35 dB    noise: -95 dBm    Flags: RSSI on-channel     Channel: 36
        '''
        
#        print "Joining access point %s" % SSID
        
        if self.mode in ['dongle']:
            join_cmds = [self.wl_prefix + 'down',
                         self.wl_prefix + 'ap 0',
                         self.wl_prefix + 'mpc 0',
                         self.wl_prefix + 'up',
                         self.wl_prefix + 'disassoc',
                         self.wl_prefix + 'join ' + SSID,
                         ]

        elif self.mode in ['nic']:
            join_cmds = [self.wl_prefix + 'down',
                         self.wl_prefix + 'ap 0',
                         self.wl_prefix + 'mpc 0',
                         self.wl_prefix + 'radio on',
                         self.wl_prefix + 'up',
                         self.wl_prefix + 'disassoc',
                         self.wl_prefix + 'join ' + SSID,
                         ]
        
#        for cmd in join_cmds:
#            time.sleep(1)
#            ret, output = self.DUT.issuecmd(cmd, True) # True means quit on error
        cmd = ';'.join(join_cmds)
        ret, output = self.DUT.issuecmd(cmd)
        if ret:
            print ret
            return True
            
        # If join successful get wl status to see what channel the AP is already on.
        time.sleep(6) # 
        cmd = self.wl_prefix + 'status'
        ret, output = self.DUT.issuecmd(cmd) # 
        print "ret: %s" % ret
        print "output: %s" % output
        
        if ret:
            print "ret: %s" % ret
            return True
        elif any(x in output for x in ['Not associated.', 'Error']):
            print output
            return True
        else:
            # Parse wl status output second line to see if it associated.
            line_dict = {'Mode:': ''}
            
            # Look for line that starts with 'Mode:'
            for line in output.splitlines():
                if line.startswith('Mode:'):
                    line_list = line.split('\t') # Split line by tabs.
            print 'line_list: {}'.format(line_list)
            
            # Split line items into key/value pairs and assign to dictionary, sample line:
            # Mode: Managed    RSSI: -47 dBm    SNR: 35 dB    noise: -95 dBm    Flags: RSSI on-channel     Channel: 36
            for item in line_list:
                items = item.split(':') # Split key/value pairs by colon.
                line_dict[items[0]] = items[1].strip() # Store key/value pairs
            
            # Check chip current channel and AP channels are the same and mode is 'Managed'.
#            if (self.get_wl_status('Channel') != line_dict['Channel']) or line_dict['Mode'] != 'Managed':
            if line_dict['Mode'] != 'Managed':
                print 'Associate unsuccessful'
                return True
            else:
                print 'Associate successful'
                return False
                           
    def check_svn_versions(self):
        ''' Check local version against repository. '''
        
        # Check if this script is the latest version.
        cmd = 'svn info'  
        local_script_revision = self.get_svn_revision(cmd)
        print "Local script directory revision is:  %s" % local_script_revision

        cmd = "svn info %s" % self.svn_script_repository 
        repository_script_revision = self.get_svn_revision(cmd)
        print "Repository script revision is: %s" % repository_script_revision
        
        if local_script_revision < repository_script_revision:
            print "Local version of script directory not up to date with latest repository version."
            print "Enter 'svn up' to update the local copy."
#            sys.exit()
#            return True
    
        # Get desired revision of golden reference files specified in config file.
        if self.operation != 'dump':
            cmd = 'svn info {}'.format(self.ref_dir)  
            local_ref_revision = self.get_svn_revision(cmd)
            print "Local reference revision is:  %s" % local_ref_revision
    
            cmd = "svn info %s" % self.svn_ref_repository 
            tob_ref_revision = self.get_svn_revision(cmd)
            print "Repository reference revision is: %s" % tob_ref_revision
            
            if self.desired_svn_ref_rev.lower() == 'tob':
                self.desired_svn_ref_rev = tob_ref_revision
                
            print "Desired reference revision: %s" % self.desired_svn_ref_rev
            
            if local_ref_revision != self.desired_svn_ref_rev:
                print "Updating local reference files to %s.\n" % self.desired_svn_ref_rev
                cmd = 'svn update --non-interactive --set-depth infinity {} --revision ' + self.desired_svn_ref_rev.format(self.ref_dir)  
    
                ret, output = self.DUT.issuecmd(cmd)
    
    def compare(self, chanspec):
        ''' Compare each register set for the chanspec passed in. '''
        
        passed_in_chanspec = chanspec
        
        if not self.associate:
            print ' '
            print "Comparing unassociated."
    
        # For each register set do the compare.
        for reg_set in self.reg_sets:
            if reg_set in ['pciephyreg', 'pmureg']:
                chanspec = 'all'
            else:
                chanspec = passed_in_chanspec
                
            if chanspec not in self.data['ref'][reg_set]:
                print "No %s reference values for chanspec: %s, skipping" % (reg_set, chanspec)
            else:
                if self.get_chip_data(reg_set, chanspec): # Get chip data into dictionaries using ignore list to filter                   
                    return True # If fail to get data return.
                else:
                    return self.compare_data('compare', reg_set, chanspec) # Saves mismatches by chanspec to self.mismatch_info[mismatch_key]
                
    def compare_data(self, mismatch_key, reg_set, chanspec):
        ''' Compare values read from reference file to values read from chip for this register set and this chanspec.
            Compares self.data['ref'] to self.data['chip']
            Save mismatches to self.mismatch_info[mismatch_key].
            mismatch_key is either 'compare' or a test name.
            
            Return True on mismatch, False if no mismatch.
        '''
        
        common_offsets = {} 
        mismatch_found = False # Bool for function return.
        self.unique_table_ids = {'ref': {}, 'chip': {}}
        self.unique_offsets = {'ref': {}, 'chip': {}}
        self.unique_regs = {'ref': {}, 'chip': {}}
    
        # Create empty mismatch dictionary, put mismatches in later if there are any.
        # mismatch key is test name if operation is test or 'compare' if operation is compare. 
        if mismatch_key not in self.mismatch_info:
            self.mismatch_info[mismatch_key] = {reg_set: {chanspec: {'reg_mismatches': {}}}}
        elif reg_set not in self.mismatch_info[mismatch_key]:
            self.mismatch_info[mismatch_key][reg_set] = {chanspec: {'reg_mismatches': {}}}
        elif chanspec not in self.mismatch_info[mismatch_key][reg_set]:
            self.mismatch_info[mismatch_key][reg_set][chanspec] = {'reg_mismatches': {}}
            
        if self.verbosity > 0:
            print "Comparing %s chip data to ref data for chanspec %s" % (reg_set, chanspec)

        try:
            # Compare ref and chip dictionaries
            if reg_set in ['phytable', 'phytbl', 'phytbl1']:
                self.mismatch_info[mismatch_key][reg_set][chanspec]['unique_table_ids'] = {}
                self.mismatch_info[mismatch_key][reg_set][chanspec]['unique_offsets'] = {'ref': {}, 'chip': {}}
    
                # Check for unique table ids found only in reference file or chip
                ref_table_ids_set, chip_table_ids_set = set(self.data['ref'][reg_set][chanspec]), set(self.data['chip'][reg_set][chanspec]) # Sets of dictionary keys
                self.mismatch_info[mismatch_key][reg_set][chanspec]['unique_table_ids']['ref'], common_table_ids, self.mismatch_info[mismatch_key][reg_set][chanspec]['unique_table_ids']['chip'] = \
                list(ref_table_ids_set - chip_table_ids_set), list(ref_table_ids_set & chip_table_ids_set), list(chip_table_ids_set - ref_table_ids_set)
                
                for source in ['ref', 'chip']:
                    if self.mismatch_info[mismatch_key][reg_set][chanspec]['unique_table_ids'][source]:
                        mismatch_found = True
    
                # Check for unique offsets in common tables
                for table_id in common_table_ids:
                    ref_offsets, chip_offsets = set(self.data['ref'][reg_set][chanspec][table_id]), set(self.data['chip'][reg_set][chanspec][table_id]) # Sets of strings (the dictionary keys)
                    self.mismatch_info[mismatch_key][reg_set][chanspec]['unique_offsets']['ref'][table_id], common_offsets[table_id], self.mismatch_info[mismatch_key][reg_set][chanspec]['unique_offsets']['chip'][table_id] = \
                    list(ref_offsets - chip_offsets), list(ref_offsets & chip_offsets), list(chip_offsets - ref_offsets)
                        
                    for source in ['ref', 'chip']:
                        if self.mismatch_info[mismatch_key][reg_set][chanspec]['unique_offsets'][source][table_id]:
                            mismatch_found = True

                    # Check for register value mismatches in common offsets
                    for offset in common_offsets[table_id]:
                        ref_value, chip_value = self.data['ref'][reg_set][chanspec][table_id][offset], self.data['chip'][reg_set][chanspec][table_id][offset]
                        if ref_value != chip_value:
                            mismatch_found = True
#                            print "table_id: %s offset: %s" % (table_id, offset)                            
#                            print "ref: %s" % ref_value
#                            print "chip: %s" % chip_value
                            if table_id not in self.mismatch_info[mismatch_key][reg_set][chanspec]['reg_mismatches']:
                                self.mismatch_info[mismatch_key][reg_set][chanspec]['reg_mismatches'][table_id] = {offset: {'ref': ref_value, 'chip': chip_value}}
                            else:
                                self.mismatch_info[mismatch_key][reg_set][chanspec]['reg_mismatches'][table_id][offset] = {'ref': ref_value, 'chip': chip_value}
            elif reg_set in ['phyreg', 'radioreg']:
                # Simple register value pairs
#                print where_am_i()    
#                print self.data['ref'][reg_set].keys()
#                print self.data['chip'][reg_set].keys()
                ref_regs_set, chip_regs_set = set(self.data['ref'][reg_set][chanspec]), set(self.data['chip'][reg_set][chanspec]) # Sets of dictionary keys
                self.unique_regs['ref'], common_regs, self.unique_regs['chip'] = list(ref_regs_set - chip_regs_set), list(ref_regs_set & chip_regs_set), list(chip_regs_set - ref_regs_set)
    
                for reg in common_regs:
                    ref_value, chip_value = self.data['ref'][reg_set][chanspec][reg], self.data['chip'][reg_set][chanspec][reg]
                    if ref_value != chip_value:
                        mismatch_found = True
#                        print "register: %s" % reg                            
#                        print "ref: %s" % ref_value
#                        print "chip: %s" % chip_value
                        if reg not in self.mismatch_info[mismatch_key][reg_set][chanspec]['reg_mismatches']:
                            self.mismatch_info[mismatch_key][reg_set][chanspec]['reg_mismatches'][reg] = {'ref': ref_value, 'chip': chip_value}
                                    
            elif reg_set == 'pciephyreg':
                # 'all' means these ref values work for all chanspecs.
#                print self.data['ref'][reg_set]['all']
                for blkaddr in self.data['ref'][reg_set]['all']:
#                    print "blkaddr: %s" % blkaddr
                    selection = self.data['ref'][reg_set]['all'][blkaddr]['selection']
                    for regaddr in self.data['ref'][reg_set]['all'][blkaddr]['regaddrs']:
#                        print "regaddr: %s" % regaddr
#                        print "ref: %s" % self.data['ref'][reg_set]['all'].keys()
#                        print "chip: %s" % self.data['chip'][reg_set][chanspec].keys()
                        ref_value = self.data['ref'][reg_set]['all'][blkaddr]['regaddrs'][regaddr]
                        chip_value = self.data['chip'][reg_set][chanspec][blkaddr]['regaddrs'][regaddr]
                        
                        # Save mismatch data in dictionaries
                        if ref_value != chip_value:
                            mismatch_found = True
#                            print "%s blkaddr: %s register: %s" % (selection, blkaddr, regaddr)                            
#                            print "ref: %s" % ref_value
#                            print "chip: %s" % chip_value
                            if blkaddr not in self.mismatch_info[mismatch_key][reg_set][chanspec]['reg_mismatches']:
#                                print mismatch_key
#                                print reg_set
#                                print chanspec
#                                print self.mismatch_info[mismatch_key][reg_set][chanspec]['reg_mismatches']
#                                print regaddr
                                
                                self.mismatch_info[mismatch_key][reg_set][chanspec]['reg_mismatches'][blkaddr] = {'selection': selection, 'regaddrs': {regaddr: {'ref': ref_value, 'chip': chip_value}}}
#                                print where_am_i()
                            else:
                                self.mismatch_info[mismatch_key][reg_set][chanspec]['reg_mismatches'][blkaddr]['regaddrs'][regaddr] = {'ref': ref_value, 'chip': chip_value}        
            elif reg_set == 'pmureg':
                # Check for unique write/read registers found only in reference file or chip
                ref_regs_set, chip_regs_set = set(self.data['ref'][reg_set]['all']), set(self.data['chip'][reg_set][chanspec]) # Sets of dictionary keys

                # Get ref unique registers, common registers of both ref and chip, and unique registers in chip data.
                self.unique_regs['ref'], common_regs, self.unique_regs['chip'] = \
                list(ref_regs_set - chip_regs_set), list(ref_regs_set & chip_regs_set), list(chip_regs_set - ref_regs_set) # Assign three lists.
                    
                # Check for unique offsets in common_regs (list of registers)
                for reg in sorted(common_regs):
#                    print "reg: %s" % (reg,)
                    
                    ref_offsets, chip_offsets = set(self.data['ref'][reg_set]['all'][reg]), set(self.data['chip'][reg_set][chanspec][reg]) # Sets of strings (the dictionary keys)
                    self.unique_offsets['ref'][reg], common_offsets[reg], self.unique_offsets['chip'][reg] = \
                    list(ref_offsets - chip_offsets), list(ref_offsets & chip_offsets), list(chip_offsets - ref_offsets)    
                    
                    # Check common offsets for register value mismatch
                    for offset in common_offsets[reg]:
                        ref_value, chip_value = self.data['ref'][reg_set]['all'][reg][offset], self.data['chip'][reg_set][chanspec][reg][offset]
#                        print "offset: %s" % offset
#                        print "ref: %s" % ref_value
#                        print "chip: %s" % chip_value
                        if ref_value != chip_value:
                            mismatch_found = True
#                            print "offset: %s" % offset                            
#                            print "ref: %s" % ref_value
#                            print "chip: %s" % chip_value
                            if reg not in self.mismatch_info[mismatch_key][reg_set][chanspec]['reg_mismatches']:
                                self.mismatch_info[mismatch_key][reg_set][chanspec]['reg_mismatches'][reg] = {offset: {'ref': ref_value, 'chip': chip_value}}
                            else:
                                self.mismatch_info[mismatch_key][reg_set][chanspec]['reg_mismatches'][reg][offset] = {'ref': ref_value, 'chip': chip_value}
            if mismatch_found:
                return True
            else:
                return False
        except KeyError as e:
#        except:
 #           print "Unexpected error in compare_data():", sys.exc_info()[0]
 #           raise
            print "Compare data KeyError: %s" % e
            print 'ref data: {}'.format(self.data['ref'])
            print 'chip data: {}'.format(self.data['chip'])
            print 'ref keys: {}'.format(self.data['ref'].keys())
            print 'chip keys: {}'.format(self.data['chip'].keys())
            print 'ref[reg_set] keys: {}'.format(self.data['ref'][reg_set].keys())
            print 'chip[reg_set] keys: {}'.format(self.data['chip'][reg_set].keys())
            return True
#            print "blkaddr: %s" % blkaddr
#            print "ref: %s" % sorted(self.data['ref'][reg_set])
#            print "chip: %s" % sorted(self.data['chip'][reg_set])
#            sys.exit()
        finally:
            self.compare_performed = True # Set flag for final print message.

    def create_csv_file(self, csv_file, csv_output_str):
        ''' Create a csv file of compare mismatches for creating html report '''
        
        # Create csv file for html report.    
        
        print csv_output_str
        
        try:
            with open(csv_file, 'w') as csvf:
                print 'Opening CSV file {}:'.format(csv_file)
                for line in csv_output_str.splitlines():
                    csvf.write(','.join(line.split()) + '\n')
                time.sleep(2) # Give time to close file
        except IOError as e:
            print e
            raise                         
                        
    def dump(self, chanspec):
        ''' Dump all tables in self.reg_sets to file. Not associated. 
            Get register values and append to file.
        '''
        
        # Get each register set's values at this chanspec and append to it's file.
        # Dump any register sets that aren't dumped yet.
        try:
            for reg_set in self.reg_sets:
                # Some register sets are same on all chanspecs so just want to dump once, not on every chanspec.
                if not self.reg_sets[reg_set]['dumped']: # Bool flag for pmureg and pciephyreg to dump just once on first chanspec
                    # Get chip data into dictionary.
                    if self.get_chip_data(reg_set, chanspec):
                        self.operation_info[self.operation][chanspec]['status'] = 'Fail'
                        self.operation_info[self.operation][chanspec]['comment'] = 'Getting chip data failed for chanspec: {}'.format(chanspec)
                        print self.operation_info[self.operation][chanspec]['comment']
                        return True

                    # Append chip data to file for this chanspec.
                    if self.dump_data_to_file(reg_set, chanspec):
                        self.operation_info[self.operation][chanspec]['status'] = 'Fail'
                        self.operation_info[self.operation][chanspec]['comment'] = "%s Dumping data to file failed." % chanspec
                        print self.operation_info[self.operation][chanspec]['comment']
                        return True
                    time.sleep(1) # wl dump fails for "wl: No clock" if we go too fast   
        except:
            (frame, filename, line_number, function_name, lines, index) = inspect.getouterframes(inspect.currentframe())[1]
            print "Unexpected error in %s." % function_name
            traceback.print_exc(file=sys.stdout)
            raise
        
        return False
            
    def dump_data_to_file(self, reg_set, chanspec):
        ''' Dump data dictionaries sorted to dump file. '''

        dump_str = [] # Build up a big list of lines then write it to file.
        
        if not ((reg_set == 'pmureg') or (reg_set == 'pciephyreg')):
            dump_str.append("chanspec %s" % chanspec) # Print chanspec for all chanspecs except pmureg and pciephyreg
    
        try:
            # Dump sorted
            if reg_set in ['phytable', 'phytbl', 'phytbl1']:
                for table_id in sorted([item for item in self.data['chip'][reg_set][chanspec]]):
                    for offset in sorted([item for item in self.data['chip'][reg_set][chanspec][table_id]]):
                        dump_str.append(' '.join(["0x{0:0{1}X}:0x{2:0{3}X} =".format(table_id, 2, offset, 4), 
                        ' '.join(["0x{0:0{1}X}".format(value, 4) for value in self.data['chip'][reg_set][chanspec][table_id][offset]])]))
                        
            elif reg_set == 'pciephyreg':
                # Miscellaneous individual registers
                for reg in self.data['chip'][reg_set][chanspec]['PCIeControlReg']['regaddrs']:
                    dump_str.append(' '.join(['PCIeControlReg ', reg, self.data['chip'][reg_set][chanspec]['PCIeControlReg']['regaddrs'][reg]]))
                
                # PCIe SerDes Registers
                dump_str.append('# PCIe SerDes Regs')
                for blkaddr in sorted([item for item in self.data['chip'][reg_set][chanspec]]):
                    if blkaddr in ['PCIeControlReg']:
                        continue # Individual registers already printed above             
                    for regaddr in [selection for selection in sorted([item for item in self.data['chip'][reg_set][chanspec][blkaddr]['regaddrs']])]:
                        dump_str.append(' '.join(["{0:>0{1}x}".format(blkaddr, 3), self.data['chip'][reg_set][chanspec][blkaddr]['selection'], "{0:>0{1}x}".format(regaddr, 2), self.data['chip'][reg_set][chanspec][blkaddr]['regaddrs'][regaddr]]))                        
                        self.reg_sets[reg_set]['dumped'] = True
            elif reg_set == 'pmureg':
                for regs in sorted([item for item in self.data['chip'][reg_set][chanspec]]):
                    write_reg, read_reg = "{0:>0{1}}".format(regs[0], 5), "{0:>0{1}}".format(regs[1], 5)
                    dump_str.append('# ' + self.pmu_names[write_reg] + ':')
                    for offset in sorted([offset for offset in self.data['chip'][reg_set][chanspec][regs]]):
                        tmp_str = ' '.join([write_reg, read_reg, hex(offset), self.data['chip'][reg_set][chanspec][regs][offset]])
                        dump_str.append(tmp_str)
                        self.reg_sets[reg_set]['dumped'] = True
            else:
                # Simple register value pairs like phyreg and radioreg.
                for reg in sorted([item for item in self.data['chip'][reg_set][chanspec]]):
                    dump_str.append(' '.join(["{0:>0{1}x}".format(reg, 3), ' '.join(self.data['chip'][reg_set][chanspec][reg])]))
                    
            dump_str = '\n'.join([line for line in dump_str]) + '\n'
            
            if self.verbosity > 0:
                print dump_str
                print ' '
                
                print "Appending %s register values to: %s" % (reg_set, self.reg_sets[reg_set]['dump_file'])
                with open(self.reg_sets[reg_set]['dump_file'], 'a') as df:
                    df.write(dump_str)
    #        except IOError as e:
    #            print e
    #            return True
        except:
            (frame, filename, line_number, function_name, lines, index) = inspect.getouterframes(inspect.currentframe())[1]
            print "Unexpected error in %s." % function_name
            traceback.print_exc(file=sys.stdout)
            return True
        
        return False

    def get_base_ref_file(self, ref_file, reg_set):
        ''' Get base data from the golden reference file passed in. '''
        
        if self.verbosity > 0:
            print "Getting data from %s base reference file:\n%s" % (reg_set, ref_file)
        
        try:
            self.get_ref_file(ref_file, reg_set)
        except IOError as e:
            print e
            print 'Check program name in config file matches nvram name.'
            raise
                    
    def get_chip_chanspec(self):
        ''' Get current chip chanspec. '''
                        
        ret, output = self.DUT.issuecmd(self.wl_prefix + 'chanspec', True)
        current_chanspec = output.split()[0]
        return current_chanspec
        
    def get_chip_data(self, reg_set, chanspec = 'unassociated'):
        ''' Get data from chip using wl dump command.
            Parse output, put data in dictionary, skip lines in ignore list.
            pciephyreg data got in get_ref_data() method.
        '''

        output_lines = []
        already_ignored_list = []
                
        if self.verbosity > 0:
            print "Getting %s data from chip" % reg_set
        ret, output = self.DUT.issuecmd('sleep 1')
        
        # 'phytable', 'phyreg', 'radioreg' gotten in different way
        if reg_set in ['phytable', 'phyreg', 'radioreg']:
            if reg_set == 'phytable':
                cmd = self.wl_prefix + 'dump phytbls'
            else:
                cmd = self.wl_prefix + 'dump ' + reg_set
            ret, output = self.DUT.issuecmd(cmd)
            
            print'ret: {}'.format(ret)
            print'output: {}'.format(output)
            
            if ret:
                print'ret: {}'.format(ret)
                return ret
            elif output in ['', -1, self.wldir + 'wl: Not Found']:
                print'output: {}'.format(output)
                return True                
            
            strings = ("Unsupported", "adapter not found")
            for line in output.splitlines():
#                print 'line: {}'.format(line)
                if any(s in line for s in strings):
                    print output
                    return True

            if reg_set in ['phyreg', 'radioreg']:
                output_lines.extend(output.splitlines()[2:]) # Skip first two lines of text
            else:
                output_lines.extend(output.splitlines())

            # Parse output, put data in dictionary, skip lines in ignore list
            last_line = ''
            for line in output_lines:
                line_list = line.strip().replace(':', ' ').replace('=', ' ').split() # Replace colon and equal sign with space then split by whitespace.
                try:
                    if reg_set in ['phytable', 'phytbl', 'phytbl1']:
                        table_id = int(line_list[0], 16) 
                        # Skip entries in ignore list
                        # Use ignore list only for compare and test not dump
                        if self.operation in ['compare', 'test']:
                            if table_id in self.ignore_list[reg_set]:
                                if table_id not in already_ignored_list:
                                    if self.verbosity > 1:
                                        print "Ignoring chip table id: %s, %s" % (hex(table_id) + ':', self.ignore_list[reg_set][table_id])
                                    already_ignored_list.append(table_id)
                                continue
                        offset = int(line_list[1], 16)
                        values = [int(value, 16) for value in line_list[2:]] # Turn string values into integers
                        
                        # Put data in dictionary.
                        if reg_set not in self.data['chip']:
                            self.data['chip'][reg_set] = {chanspec: {table_id: {offset: values}}}
                        if chanspec not in self.data['chip'][reg_set]:
                            self.data['chip'][reg_set][chanspec] = {table_id: {offset: values}}
                        elif table_id not in self.data['chip'][reg_set][chanspec]:
                            self.data['chip'][reg_set][chanspec][table_id] = {offset: values}
                        else:
                            self.data['chip'][reg_set][chanspec][table_id][offset] = values # List of values
                    elif reg_set in ['phyreg', 'radioreg']:
                        # Simple register value pairs
                        reg = int(line_list[0], 16)
                        values = line_list[1:]
                        
                        # Skip entries in ignore list
                        if reg in self.ignore_list[reg_set]:
                            if reg not in already_ignored_list:
                                if self.verbosity > 1:
                                    print "Ignoring chip reg: %s" % hex(reg)
                                already_ignored_list.append(reg)
                            continue
                                                
                        if reg_set not in self.data['chip']:
                            self.data['chip'][reg_set] = {chanspec: {reg: values}}
                        elif chanspec not in self.data['chip'][reg_set]:
                            self.data['chip'][reg_set][chanspec] = {reg: values}
                        else:
                            self.data['chip'][reg_set][chanspec][reg] = values
                except (IndexError, ValueError) as e:
                    print e
                    if self.verbosity > 0:
                        print "Incomplete line from device:\n%s" % line
                        print "Last line:\n%s" % last_line
                    continue
        # These gotten in different way    
        elif reg_set == 'pciephyreg':
            ret = self.get_pciephyreg_data(reg_set, chanspec)
        elif reg_set == 'pmureg':
            ret = self.get_pmu_data(reg_set, chanspec)
                
        if ret:
            return ret
        else:
            return False

    def get_chip_info(self):
        ''' Get chip number and phy revision from wl revinfo 
            1. If alpha characters in wl revinfo then it's a hex number.
            2. If in config file use that.
            3. Use wl revinfo number.        
        '''

        cmd = 'revinfo'
        ret, output = self.DUT.issuecmd(cmd, cmdtype='WL')
        
        if ret:
            "%s failed" % cmd
            print ret
            return True

        for line in output.splitlines():
            if 'chipnum' in line:
                self.chip_num = line.split()[1][2:]
                if re.search('[a-zA-Z]', self.chip_num):
                    print "chip_num is hex: %s" % self.chip_num
                    self.chip_num = int(self.chip_num, 16)
            elif 'chiprev' in line:
                self.chip_rev = line.split()[1][2:]
            elif 'phyrev' in line:
                self.phy_rev = line.split()[1][2:]
                    
        if (self.chip_num == '4345') and (int(self.chip_rev, 16) > 1):
            self.chip_num = '43452'
                    
        print "chip_num: %s" % self.chip_num            
        print "phy_rev: %s" % self.phy_rev
                    
    def get_diff_ref_file(self, ref_file, reg_set):
        ''' Get branch diff data from the golden reference file passed in. '''
        
        if self.verbosity > 0:
            print "Getting data from diff reference file:\n%s" % ref_file
        
        try:
            self.get_ref_file(ref_file, reg_set)
        except IOError as e:
            if self.verbosity > 0:
                print e
                print "Branch diff file not found, using base ref values."
                print
            return None
        
        if self.verbosity > 0:
            print ' '
            print "Branch diff file found, updating base ref values."
            print ' '
            
    def get_ignore_list_file(self, reg_set):
        """ Get list of registers to ignore during compare.
            phyreg, phytable and radioreg ignore files just have register addresses.
            pciephyreg ignore file has block address and register address.
        """
        
        ignore_file = "%s%s%s%s%s_%s_%s_ignorelist.txt" % (self.ref_dir, self.os_path_sep, self.chip_num, self.os_path_sep, self.phy_rev, self.program, reg_set)            

        if self.verbosity > 0:
            print "Getting data from ignore file:\n%s" % ignore_file
        
        # Open the file, get the lines of data, put in dictionary.
        try:
            with open(ignore_file) as f:
                for line in f:
                    if not line.strip():
                        continue # Skip blank lines
                    else:
                        line_items = line.strip().split()
    
                    if reg_set in ['pciephyreg']:
                        blkaddr = int(line_items[0], 16) # blkaddr will have a list of registers to ignore for that blkaddr.
                        regaddr = int(line_items[2], 16) # Convert to integers for sorting later. 
                        
                        # Add the blkaddrs and regaddrs to the dictionary.
                        if reg_set not in self.ignore_list:
                            self.ignore_list[reg_set] = {blkaddr: [regaddr]} # Add 'pciephyreg' key, dictionary as value.
                        elif blkaddr not in self.ignore_list[reg_set]:
                            self.ignore_list[reg_set][blkaddr] = [regaddr] # Add blkaddr dictionary with list of regaddrs to ignore as value. 
                        else:
                            self.ignore_list[reg_set][blkaddr].append(regaddr) # The blkaddr is already there, append this regaddr to it's list.
                    else:
                        # Registers to ignore for that register set.
                        self.ignore_list[reg_set][int(line_items[0], 16)] = line_items[1] # Turn register hex value to int
        except IOError as e:
            print e
            print "Ignore list file not found, using all values in reference file.\n"
        
    def get_pciephyreg_data(self, reg_set, chanspec):
        ''' Build up big long string of ';' separated dhd commands to send all at once.
            Save all locations in a list so we can match the data up when we get it back.
            Data comes back in one big chunk.
            Put data in self.data.
        '''
        
        register_info = {'000': {'selection': 'ieee0Blk_A',
                                 'regaddrs': ['00', '01', '02', '03', '04', '05', '06', '07', '08', '09', '0a', '0b', '0c', '0d', '0e', '0f']},
                         '001': {'selection': 'ieee1Blk_A',
                                 'regaddrs': ['00', '01', '02', '03', '04', '05', '06', '07', '08', '09', '0a', '0b', '0c', '0d', '0e', '0f']},
                         '800': {'selection': 'XgxsBlk0_A',
                                 'regaddrs': ['10', '11', '12', '13', '14', '15', '16', '17', '18', '19', '1a', '1b', '1c', '1d', '1e']},
                         '801': {'selection': 'XgxsBlk1_A',
                                 'regaddrs': ['14', '15', '16', '17', '18', '19', '1a', '1b', '1c', '1d', '1e']},
                         '802': {'selection': 'XgxsBlk2_A',
                                 'regaddrs': ['10', '11', '12', '13', '14', '15', '16', '17', '18', '19', '1a', '1b', '1c', '1d', '1e']},
                         '803': {'selection': 'XgxsBlk3_A',
                                 'regaddrs': ['10', '11', '12', '13', '14', '15', '16', '17', '18', '19', '1a', '1b', '1c', '1d', '1e']},
                         '804': {'selection': 'XgxsBlk4_A',
                                 'regaddrs': ['10', '11', '12', '13', '14', '15', '16', '17', '18', '19', '1a', '1b', '1c', '1d', '1e']},
                         '808': {'selection': 'TxPll_A',
                                 'regaddrs': ['10', '11', '12', '13', '14', '15', '16', '17', '18', '1a', '1b', '1c', '1d', '1e']},
                         '809': {'selection': 'TxPll2_A',
                                 'regaddrs': ['10', '11', '12', '13', '14', '15', '16', '17', '18', '1a', '1b', '1c', '1d', '1e']},
                         '820': {'selection': 'Tx0_A',
                                 'regaddrs': ['10', '11', '12', '13', '14', '15', '16', '17', '18', '1a', '1b', '1c', '1d', '1e']},
                         '840': {'selection': 'Rx0_A',
                                 'regaddrs': ['10', '11', '12', '14', '15', '16', '17', '18', '1a', '1b', '1c', '1d', '1e']},
                         '850': {'selection': 'Rx0_G2_A',
                                 'regaddrs': ['10', '11', '12', '13', '14', '15', '16', '17', '18', '1a', '1b', '1c', '1d', '1e', '1f']},
                         '861': {'selection': 'TxB_A',
                                 'regaddrs': ['10', '11', '12', '13', '14', '15', '16', '17', '18', '1a', '1b', '1c', '1d', '1e']},
                         '862': {'selection': 'RxB_A',
                                 'regaddrs': ['10', '11', '12', '14', '15', '16', '17', '18', '1a', '1b', '1c', '1d', '1e']},
                         '863': {'selection': 'RxB_G2_A',
                                 'regaddrs': ['10', '11', '12', '13', '14', '15', '16', '17', '18', '1a', '1b', '1c', '1d', '1e', '1f']},
                         }


        command_string = ''
        locations = [] # Save all locations in a list so we can match up the data when we get it back. List of strings.
        cmd_prefix = {'nic': self.wl_prefix + 'pcieserdesreg', 'dongle': self.dhd_prefix + 'pciecorereg'}
                        
        # Get PCIeControlReg first.        'PCIeControlReg': {'selection': '', 'regaddrs': ['0x0']}
        if self.mode == 'dongle':
            cmd = self.dhd_prefix + 'pciecorereg 0x0'
        elif self.mode == 'nic':
            cmd = self.wl_prefix + 'corereg 3 0x0'
        
        ret, output = self.DUT.issuecmd(cmd)
        if ret:
            print "ret: %s" % ret
            print "output: %s" % output
            return ret

        # Remove first two '0x' hex characters.
        if output.startswith('0x'):
            output_value = output[2:].strip()
        else:
            output_value = output.strip()
        
        # Put PCIeControlReg data in dictionary.
        if reg_set not in self.data['chip']:
            self.data['chip'][reg_set] = {chanspec: {'PCIeControlReg': {'selection': '', 'regaddrs': {'0x0': output_value}}}}
        elif chanspec not in self.data['chip'][reg_set]:
            self.data['chip'][reg_set][chanspec] = {'PCIeControlReg': {'selection': '', 'regaddrs': {'0x0': output_value}}}

        for blkaddr in sorted(register_info):
#            print 'blkaddr: ' + blkaddr
            selection = register_info[blkaddr]['selection']
            for regaddr in sorted(register_info[blkaddr]['regaddrs']):
#                print "regaddr %s " % regaddr
                locations.append(','.join([blkaddr, selection, regaddr])) # Save locations to list so we can match up the data later.
#                print locations
                if (blkaddr == 2112 or 2146) and (regaddr == 16):
                    continue # blkaddr 804, 862 regaddr 10 are status registers that change and are never the same, multiple reads always fail.

                # The commands to read one register address.
                if self.mode == 'dongle':
                    command_string += cmd_prefix[self.mode] + ' 0x128 0x1f02;'
                    command_string += cmd_prefix[self.mode] + ' 0x12c 0x8000' + blkaddr + '0;'
                    command_string += cmd_prefix[self.mode] + ' 0x128 0x2000' + regaddr + '02;'
                    command_string += cmd_prefix[self.mode] + ' 0x130;'
                elif self.mode == 'nic':
                    command_string += cmd_prefix[self.mode] + ' 0x' + blkaddr + ' 0x' + regaddr + ';'

#                print "command_string: %s" % command_string
                ret, output = self.DUT.issuecmd(command_string) # Send the whole command string.
                
                #TODO Instead of sending command string append to file then send to DUT to execute.
        
                if ret:
                    print "ret: %s" % ret
                    print "output: %s" % output
                    return ret
                
                if output.strip() in ['NO OUTPUT']:
                    print "output: %s" % output
                    return ret
                           
                # Parse output to dictionary.
                for location, line in zip(locations, output.splitlines()):  
#                    print "location: %s" % location
#                    print "line: %s" % line
                    if self.mode == 'dongle':
                        output_value = line[6:].strip() # Strip off first six characters, get character 6 to end, 0x800001a0 becomes 01a0.
                    elif self.mode == 'nic':
                        output_value = "{0:0>{1}}".format(line[2:].strip(), 5) # 
                        
                    blkaddr, selection, regaddr = location.split(',')
#                    print "blkaddr: %s" % blkaddr
#                    print "selection: %s" % selection
#                    print "regaddr: %s" % regaddr
                    
                    # Save chip data in dictionaries, if blkaddr not 'PCIeControlReg' turn blkaddr to int.
                    if blkaddr != 'PCIeControlReg':
                        blkaddr = int(blkaddr, 16) # Store as integer for sorting.
                        regaddr = int(regaddr, 16) # Store as integer for sorting.
                    
                    if reg_set not in self.data['chip']:
                        self.data['chip'][reg_set] = {chanspec: {blkaddr: {'selection': selection, 'regaddrs': {regaddr: output_value}}}}
                    elif chanspec not in self.data['chip'][reg_set]:
                        self.data['chip'][reg_set][chanspec] = {blkaddr: {'selection': selection, 'regaddrs': {regaddr: output_value}}}
                    elif blkaddr not in self.data['chip'][reg_set][chanspec]:
                        self.data['chip'][reg_set][chanspec][blkaddr] = {'selection': selection, 'regaddrs': {regaddr: output_value}}
                    else:
                        self.data['chip'][reg_set][chanspec][blkaddr]['regaddrs'][regaddr] = output_value
                        self.data['chip'][reg_set][chanspec][blkaddr]['selection'] = selection
            
                    if blkaddr != 'PCIeControlReg':
                        blkaddr = hex(blkaddr) # Turn back to hex string.
                        regaddr = hex(regaddr) # Turn back to hex string.
                
                locations = [] # Clear the list each loop.
                command_string = '' # Reset command string. Have to do by reg_addr or command string gets to long and times out.
                                    # Could send commands in file and execute on DUT, future todo.
        return False
                
    def get_pmu_data(self, reg_set, chanspec):
        ''' PMU CoreCapabilities (Chipcommon Offset 0x604)  
            CoreRev                    7:0     This field specifies the core revision of PMU.
            ResourceCnt (RC)          12:8     This field contains the number of resources supported by this PMU.
            ResourceReqTimerCnt (TC) 16:13     This field contains the number of Resource Request Timers supported by this PMU.
            PLLControlCnt (PC)       21:17     This field contains the number of PLL Control registers supported by this PMU.
            RegulatorControlCnt (VC) 26:22     This field contains the number of Voltage Regulator Control registers supported by this PMU.
            ChipControlCnt (CC)      31:27     This field contains the number of Chip Control registers supported by this PMU. 
            
                GCI CoreCapabilities 1 (Offset 0x4) 
            NumChipControlReg         11:8     This bit indicates how many chip control registers are supported for this CHIP. (0 means none.) 
    
            Write registers:
            pll_control 0x660
            pmu_control 0x650
            gci_control 0xc40
            vreg_control 0x658
            pmu_dependency 0x620
         '''
        
        locations = [] # Save all locations in a list so we can match the data up when we get it back.
        command_string = ''
#        ret = 0

        # Info to get number of registers (max registers, for max_reg below)
        bit_info = {'0xc04': {('0xc40', '0xe00'): {'mask': 0x00000f00, 'lsb': 8}}, # gci_control
                    '0x604': {('0x660', '0x664'): {'mask': 0x003e0000, 'lsb': 17}, # pll_control
                              ('0x658', '0x65c'): {'mask': 0x07c00000, 'lsb': 22}, # vreg_control
                              ('0x650', '0x654'): {'mask': 0xf8000000, 'lsb': 27}, # pmu_control
                              }
                    }
                                
        # write_reg, read_reg tuple is dictionary key.
        pmu_info = {('0x620', '0x624'): {'max_reg': 30}, # Already have this max register, don't need to get below.
                    ('0x620', '0x628'): {'max_reg': 30}, # Already have this max register, don't need to get below. 
                    ('0x650', '0x654'): {'max_reg': ''}, # Use bit_info above to get these max_regs...
                    ('0x658', '0x65c'): {'max_reg': ''}, 
                    ('0x660', '0x664'): {'max_reg': ''}, 
                    ('0xc40', '0xe00'): {'max_reg': ''},
                    }
                 
        # Read 0xc04 and 0x604, mask off appropriate bits to get number of control registers, fill in pmu_info max_reg.
        # Just need to get the four above that arn't filled in, already have ('0x620', '0x624') and ('0x620', '0x628').
        for reg in bit_info:
            if self.mode == 'nic':
                ret, output = self.DUT.issuecmd("%swl ccreg %s" % (self.wldir, reg))
                if ret:
                    print ret
                    raise IOError
                data = output          
            elif self.mode == 'dongle':
                ret, output = self.DUT.issuecmd("%sdhd -i eth1 sbreg %s" % (self.wldir, reg))
                if ret:
                    print ret
                    raise IOError
                print output
#                sys.exit()
                data = output.splitlines()[1]          
            
            # Fill in max register info for pmu_info
            for regs, mask_info in bit_info[reg].iteritems():
                result = int(data, 16) & mask_info['mask'] 
                result >>= mask_info['lsb']
                pmu_info[regs]['max_reg'] = result # Fill in max register info in pmu_info for these regs.
#                print "regs: %s max register: %s" % (regs, pmu_info[regs]['max_reg'])
                            
        # Build up big long string of ';' separated commands to send all at once.
        for regs, max_info in sorted(pmu_info.iteritems()):
            for offset in range(max_info['max_reg']):  
                write_reg, read_reg = regs[0], regs[1]
                locations.append(','.join([','.join(regs), str(offset)])) # Save locations to list so we can match up to returned data later.
                if self.mode == 'nic':
                    command_string += "%swl ccreg  %s %s;" % (self.wldir, write_reg, hex(offset)) # Write to a register.
                    command_string += "%swl ccreg %s;" % (self.wldir, read_reg) # Read from this one.
                elif self.mode == 'dongle':
                    command_string += self.dhd_prefix + "sbreg %s %s;" % (write_reg, hex(offset)) # Write to a register.
                    command_string += self.dhd_prefix + "sbreg %s;" % read_reg # Read from this one.
                
#        print "command_string: %s" % command_string
        ret, output = self.DUT.issuecmd(command_string) # Send the whole command string.

        if ret:
            print "ret: %s" % ret
            print "output: %s" % output
            return ret
            
        # Parse output to dictionary.
        # Get every other line of output since we took two readings at each location, keep second reading.
        every_third_line_from_output = [line for line in itertools.islice(output.splitlines(), 2, None, 3)] # 1: from the third line ([1]), None: to the end, 3: step  
        
#        print locations
        # Match up register location with data returned, one location for each data returned.
        for location, line in zip(locations, every_third_line_from_output):  
            write_reg, read_reg, offset = location.split(',')
            offset = int(offset) # Store as int for sorting.
            regs = (write_reg, read_reg) # Put back to tuple for dictionary key.
#            print "location: %s" % location
#            print "regs, offset: %s, %s" % (regs, offset)
#            print "line: %s" % line
            if self.mode == 'nic':
                chip_value = "0x{0:>0{1}x}".format(int(line.strip(), 16), 8)
#                print "chip value %s" % chip_value
#                print "0x{0:>0{1}x}".format(int(line.strip(), 16), 8)
            elif self.mode == 'dongle':
                chip_value = line
            
            # Put data in main data dictionary.
            if reg_set not in self.data['chip']:
                self.data['chip'][reg_set] = {chanspec: {regs: {offset: chip_value}}}
            elif chanspec not in self.data['chip'][reg_set]:
                self.data['chip'][reg_set][chanspec] = {regs: {offset: chip_value}}
            elif regs not in self.data['chip'][reg_set][chanspec]:
                self.data['chip'][reg_set][chanspec][regs] = {offset: chip_value}
            else:
                self.data['chip'][reg_set][chanspec][regs][offset] = chip_value
                            
    def get_ref_data(self, reg_set):
        ''' Get all the data from all the reference files into dictionaries.
            First get the base reference file then any branch diff file if it exists.
            Files with branch in the name are diff files.
            Update ref dictionary with diff values. 
            
            base_ref_file = <chip>_<phy rev>_<program>_<register set>_ref.txt
            diff_ref_file = <chip>_<phy rev>_<branch>_<program>_<register set>_ref.txt
        '''
        
        print ' '
        print "Getting golden reference values for %s from ref files." % self.chip_num
        
        # Get one file at a time and put it's data in self.data['ref'][reg_set][chanspec]
        base_ref_file = "%s%s%s%s_%s_%s_ref.txt" % (self.ref_dir, self.chip_num, self.os_path_sep, self.phy_rev, self.program, reg_set)               
        diff_ref_file = "%s%s%s%s_%s_%s_%s_ref.txt" % (self.ref_dir, self.chip_num, self.os_path_sep, self.phy_rev, self.branch, self.program, reg_set)               

        self.get_base_ref_file(base_ref_file, reg_set) # Get base golden reference values into dictionary
        self.get_diff_ref_file(diff_ref_file, reg_set) # Overwrite base values with branch diff values
        
    def get_ref_file(self, ref_file, reg_set):
        ''' Get data from the golden reference file passed in. '''
        
        with open(ref_file) as f:
            self.parse_ref_file_lines(f, reg_set)

    def get_reg_names(self, reg_set, chanspec):
        ''' Get register set names from file. 
            Already have ref data so will add to that dictionary.
        '''
        
        reg_set_file = '{}{}{}{}_register_names.txt'.format(self.ref_dir, self.chip_num, self.os_path_sep, reg_set)
        self.reg_names[reg_set] = {}
             
        print 'Getting {} register names'.format(reg_set) 
        
        try:
            with open(reg_set_file) as f:
                for line in f.readlines():
#                    print line
                    reg, name = line.split()
                    reg = int(reg)
#                    print 'reg: {} name: {}'.format(reg, name)
                    # Except registers that don't have a name.
#                    print 'chanspec: {}'.format(chanspec)
#                    print self.data['ref'][reg_set][chanspec].keys()
#                    print self.data['ref'][reg_set][reg]
                    self.reg_names[reg_set][reg] = name
        except IOError as e:
            print e
            return True
        
        return False
                       
    def get_svn_revision(self, cmd):
        ''' Issue command, parse data for revision. '''
        
        print "cmd: %s" % cmd
        ret, output = self.DUT.issuecmd(cmd)
        
        print "ret: %s" % ret
        print "output: %s" % output

        if output == '-1':
            print 'NO OUTPUT'
            return True
        else:    
            for line in output.splitlines():
    #            if line.startswith("Revision"):
                if line.startswith("Last Changed Rev:"):
                    return line.split()[3].strip()

    def get_wl_pwrstats_pcie(self,):
        ''' Get wl pwrstats info for just the PCIE section, return it as a dictionary.  '''
        
        ret, output = self.DUT.issuecmd(self.wl_prefix + 'pwrstats')    
        print "ret: %s" % ret
        ret = 0 # temp bug fix
        print "ret: %s" % ret
        
        if ret:
            print "ret: %s" % ret
            print "output: %s" % output
            return ret
        else:
#            print output
            wl_pwrstats_pcie = {}
            
            # Look for PCIE: section in wl pwrstats output to get sleep counts.
            lines = output.splitlines()
            for index, line in enumerate(lines):
                if line == 'PCIE:':
#                    print "PCIE line number: %s" % index
                    wl_pwrstats_pcie_section = '\n'.join(lines[index:index + 16]) # 16 lines from the output starting from index.
#                    print wl_pwrstats_pcie_section
                    
                    # Get keys and values from PCIE section of output into dictionary.
                    for line in wl_pwrstats_pcie_section.splitlines():
                        items = line.split(':')
                        if len(items) == 2:
                            key, value = items[0].strip(), items[1].strip()
                            wl_pwrstats_pcie[key] = value
                        else:
                            # Link substates have more than two items in a line.
                            items = line.split() # Split by whitespace, first item is parent key, rest are sub-keys:values.
                            wl_pwrstats_pcie[items[0]] = {items[1].split(':')[0]: items[1].split(':')[1], \
                                                          items[2].split(':')[0]: items[2].split(':')[1]}
            return wl_pwrstats_pcie # dictionary
                    
    def get_wl_interface(self):
        ''' Get wireless interface. '''
        
        # Get network interface for wireless IP address.
        cmd = 'cat /proc/net/wireless'
        ret, output = self.DUT.issuecmd(cmd)
        if ret:
            print "ret %s" % ret
            return ret
        else:
            try:
                self.wl_intf = output.splitlines()[2].split(':')[0].strip()
                print 'wireless interface: {}'.format(self.wl_intf)
                
                self.dhd_prefix = "%sdhd -i %s " % (self.wldir, self.wl_intf)
                self.wl_prefix = "%swl -i %s " % (self.wldir, self.wl_intf)
    #            self.dhd_prefix = "%sdhd -i %s " % (self.wldir, self.wl_intf)
    #            self.wl_prefix = "-i %s " % self.wl_intf
            except IndexError as e:
                print e
                return True

            return False
                
    def get_wl_status_item(self, param):
        ''' Get wl status line into dictionary, return the paramater passed in.
            Mode: Managed    RSSI: -47 dBm    SNR: 35 dB    noise: -95 dBm    Flags: RSSI on-channel     Channel: 36
        '''
        
        line_dict = {}
        
        ret, output = self.DUT.issuecmd(self.wl_prefix + 'status') # 
        line_list = output.splitlines()[1].split('\t') # Split line by tabs
        
        # Split line items into key/value pairs and assign to dictionary
        # Mode: Managed    RSSI: -47 dBm    SNR: 35 dB    noise: -95 dBm    Flags: RSSI on-channel     Channel: 36
        for item in line_list:
            items = item.split(':') # Split key/value pairs by colon.
            line_dict[items[0]] = items[1].strip() # Store key/value pairs
            
        return line_dict[param]
                
    def issuecmd(self, cmd, verbosity, quit_on_error=False):
        ''' Send command to OS. 
            verbosity = 1, Show commands
            verbosity = 2, Show return code
            verbosity = 3, Show output
            
        '''
            
        try:
            if self.dut_os in ['Darwin']:
                cmd = 'sudo ' + cmd
        except AttributeError as e:
            pass
#            print e # Except AttributeError, the first time we won't know what os is yet. 
        
        if self.verbosity > 0:
            print "Issue cmd: %s" % cmd
            
        try:
#            proc = subprocess.Popen(cmd_list, stdout = subprocess.PIPE, stderr = subprocess.PIPE, shell=True)
#            proc = subprocess.Popen(cmd.split(), stdout = subprocess.PIPE, stderr = subprocess.PIPE)
            with tempfile.TemporaryFile() as tmpFile:
#                print shlex.split(cmd)
#                proc = subprocess.Popen(shlex.split(cmd), stdout=tmpFile.fileno())
                proc = subprocess.Popen(cmd, stdout=tmpFile.fileno(), shell=True)
#                output, ret = proc.communicate()
                
                ret = proc.wait()
                output = ''.join(tmpFile.readlines())
                
                if verbosity > 1:
                    print "return code: %s" % ret
                if verbosity > 2:
                    print "output: \n%s" % output

                if ret:
#                    print "return: %s" % ret
                    if quit_on_error:
#                        print "quit"
                        sys.exit()
                        
                return (ret, output)
        except subprocess.CalledProcessError as e:
            print "Subprocess Error: %s" % e
            raise
                            
    def load_driver(self):
        ''' Firmware load, install driver, get wireless ethernet port then load firmware. '''

        cmd_delay = .1 # Delay between commands, if we go too fast sometimes bad things happen.
        
        load_driver_cmds = ['rmmod dhd',
                            'insmod ' + self.wldir + 'dhd.ko',
                            ]
        
        print "Installing driver"
        
        # Install driver.
        try:            
            for cmd in load_driver_cmds:
                ret, output = self.DUT.issuecmd(cmd)
                "sleep %s" % cmd_delay,
                
                if ret:
                    if 'rmmod' in cmd:
                        continue # Allow module not loaded error
                    else:
                        print "ret %s" % ret
                        return ret
                    
        except OSError as e:
            print e
            print "Error loading driver."
            return None
        
    def load_firmware(self):
        ''' Firmware load, install driver, get wireless ethernet port then load firmware. '''

        cmd_delay = .1 # Delay between commands, if we go too fast sometimes bad things happen.
        
        load_fw_cmds = [self.wldir + "dhd -i %s download %s %s" % (self.wl_intf, self.wldir + self.wlfw, self.wldir + self.wlnv),
                        "sleep %s" % cmd_delay,
                        "ifconfig eth1 %s up" % self.config['DUTS']['0']['intf']['0']['ip'],
                        "sleep %s" % cmd_delay,
#                        self.wl_prefix + 'down',
#                        "sleep %s" % cmd_delay,
#                        self.wldir + "wl -i eth1 clmload %s" % self.wldir + self.wlclm,
#                        "sleep %s" % cmd_delay,
#                        self.wl_prefix + 'up',
#                        "sleep %s" % cmd_delay,
                        ]
                
        # Load firmware.
        try:            
            print "Loading firmware"
            
            # Load firmware.
            for cmd in load_fw_cmds:
                ret, output = self.DUT.issuecmd(cmd)
                
                if ret:
                    print "ret %s" % ret
                    return ret
        except OSError as e:
            print e
            print "Error loading firmware."
            return True
        
        ret, self.wl_ver = self.DUT.issuecmd(self.wl_prefix + 'ver')
        
        if ret:
            print ret
            return True
                
        print self.wl_ver 
        
        if 'adapter not found' in output:
            print 'Wireless adapter not found, load firmware?'
            return True
  
        
    def parse_ref_file_lines(self, ref_file, reg_set):
        ''' Parse the lines in the golden reference file and store in self.data dictionary by chanspec. 
            chanspec defaults to 'all', if the word 'chanspec' appears in the reference file the following values will be stored under that chanspec key.
        '''
        
        chanspec = 'all' # Dictionary key for register sets that don't have any chanspec in the reference file
        already_ignored_list = [] # Save here so we just print them once
        
        if reg_set != 'pmureg':
            self.get_ignore_list_file(reg_set) # Get ignore list into dictionaries, no ignore list for pmureg and pciephyreg.               

        for line in ref_file:
#            print "line: %s" % line
            if not line.strip() or line.startswith('#'):
                continue # Skip blank lines and comments
            else:
                line_list = line.strip().split() # Split line into list of pieces.
                
                if line.lower().startswith('chanspec'):
                    chanspec = line_list[1]
                    if self.verbosity > 0:
                        print "Found %s reference values for chanspec: %s" % (reg_set, chanspec)
                    continue

            try:
                if reg_set in ['phytable', 'phytbl', 'phytbl1']:
                    table_id = int(line_list[0].split(':')[0], 16) 
                    offset = int(line_list[0].split(':')[1], 16)
                    values = [int(value, 16) for value in line_list[2:]] # Turn string values into integers

                    # Skip things in the ignore list
                    if reg_set in self.ignore_list:
                        if table_id in self.ignore_list[reg_set]:
                            if table_id not in already_ignored_list:
                                if self.verbosity > 1:
                                    print "Ignoring ref table id: %s, %s" % (hex(table_id) + ':', self.ignore_list[reg_set][table_id])
                                already_ignored_list.append(table_id)
                            continue
                    
                    if reg_set not in self.data['ref']:
                        self.data['ref'][reg_set] = {chanspec: {}}
                        self.data['ref'][reg_set][chanspec] = {table_id: {}}
                        self.data['ref'][reg_set][chanspec][table_id] = {offset: values}
                    elif chanspec not in self.data['ref'][reg_set]:
                        self.data['ref'][reg_set][chanspec] = {table_id: {}}
                        self.data['ref'][reg_set][chanspec][table_id] = {offset: values}
                    elif table_id not in self.data['ref'][reg_set][chanspec]:
                        self.data['ref'][reg_set][chanspec][table_id] = {offset: values}
                    else:
                        self.data['ref'][reg_set][chanspec][table_id][offset] = values # List of values
                    
                elif reg_set == 'pciephyreg':
                    if line_list[0] == 'PCIeControlReg':
                        blkaddr = line_list[0]
                        selection = ''
                        regaddr = line_list[1]
                        default = line_list[2]   
                    else:    
                        blkaddr = int(line_list[0], 16) # Store as integers for sorting
                        selection = line_list[1]
                        regaddr = int(line_list[2], 16) # Store as integers for sorting
                        default = line_list[3]   
                    
                    if reg_set in self.ignore_list:
                        if blkaddr in self.ignore_list[reg_set]:
                            if regaddr in self.ignore_list[reg_set][blkaddr]:
                                if str(blkaddr) + '_' + str(regaddr) not in already_ignored_list:
                                    if self.verbosity > 1:
                                        print "Ignoring blkaddr regaddr: %s, %s" % (hex(blkaddr), hex(regaddr))
                                    already_ignored_list.append(str(blkaddr) + '_' + str(regaddr))
                                continue
                    
                    # Save ref data in dictionaries
                    if reg_set not in self.data['ref']:
                        self.data['ref'][reg_set] = {chanspec: {blkaddr: {'selection': selection, 'regaddrs': {regaddr: default}}}}
                    elif chanspec not in self.data['ref'][reg_set]:
                        self.data['ref'][reg_set][chanspec] = {blkaddr: {'selection': selection, 'regaddrs': {regaddr: default}}}
                    elif blkaddr not in self.data['ref'][reg_set][chanspec]:
                        self.data['ref'][reg_set][chanspec][blkaddr] = {'selection': selection, 'regaddrs': {regaddr: default}}
                    else:
                        self.data['ref'][reg_set][chanspec][blkaddr]['regaddrs'][regaddr] = default
                        self.data['ref'][reg_set][chanspec][blkaddr]['selection'] = selection

                elif reg_set == 'pmureg':
                    regs = (line_list[0], line_list[1])
                    offset = int(line_list[2], 16)
                    default = line_list[3]   
                    
                    if reg_set not in self.data['ref']:
                        self.data['ref'][reg_set] = {chanspec: {regs: {offset: default}}}
                    elif chanspec not in self.data['ref'][reg_set]:
                        self.data['ref'][reg_set][chanspec] = {regs: {offset: default}}
                    elif regs not in self.data['ref'][reg_set][chanspec]:
                        self.data['ref'][reg_set][chanspec][regs] = {offset: default}
                    else:
                        self.data['ref'][reg_set][chanspec][regs][offset] = default
                elif reg_set in ['phyreg', 'radioreg']:
                    # Simple register value pairs
                    reg = int(line_list[0], 16)
                    values = line_list[1:]

                    # Skip entries in ignore list
                    if reg_set in self.ignore_list:
                        if reg in self.ignore_list[reg_set]:
                            if reg not in already_ignored_list:
                                if self.verbosity > 1:
                                    print "Ignoring ref reg: %s" % hex(reg)
                                already_ignored_list.append(reg)
                            continue
                                        
                    # Add values to dictionary.
                    if reg_set not in self.data['ref']:
                        self.data['ref'][reg_set] = {chanspec: {reg: values}}
                    if chanspec not in self.data['ref'][reg_set]:
                        self.data['ref'][reg_set][chanspec] = {reg: values}
                    elif reg_set not in self.data['ref'][reg_set][chanspec]:
                        self.data['ref'][reg_set][chanspec][reg] = values
                    else:
                        self.data['ref'][reg_set][chanspec][reg] = values
            except IndexError as e:
                print e
                print "Incomplete record in reference file: %s" % line
                raise

    def print_compare_summary(self):
        ''' Make one big list of output strings then append them to mismatch file.
            mismatch_key is testname if operation is test, or register set if operation is compare.
        '''
        
        csv_output_string_list = {} # List of strings to be written to each register set's csv file.
        output_string_list = {} # List of strings for each register set to be written to it's mismatch file.
        csv_files = {} # CSV filename for each register set.
        mismatch_files = {} # Mismatch filename for each register set.

        print ' '
        print "Printing summary"
        
        # Which register sets have mismatch info.
#        print [[reg_set for reg_set in self.mismatch_info[mismatch_key]] for mismatch_key in self.mismatch_info]
               
        # If there's keys there's mismatches.
        # Only create mismatch files for register sets that have mismatches.
        if self.mismatch_info:
            # Create mismatch file for each register set that has mismatches.
            for mismatch_key in sorted(self.mismatch_info): # mismatch_key could be like; compare, test1, test2...
                # Each register set's output list of strings (if any) will be written to it's own mismatch file.
#                print self.mismatch_info[mismatch_key]
                for reg_set in self.mismatch_info[mismatch_key]:
                    for chanspec in self.mismatch_info[mismatch_key][reg_set]:
                        if self.mismatch_info[mismatch_key][reg_set][chanspec]['reg_mismatches']:
#                            print self.mismatch_info[mismatch_key][reg_set][chanspec]
                            print 'Create {} file'.format(reg_set)
                            # Create mismatch file, if a file suffix was passed in use it or use date/time in file name.
                            if hasattr(self, 'file_suffix'):
                                csv_files[reg_set] = '{}\{}_{}_{}_{}_mismatch_{}.csv'.format(self.testDetails.testresultdir, self.chip_num, self.phy_rev, self.operation, reg_set, self.file_suffix)
                                mismatch_files[reg_set] = '{}\{}_{}_{}_{}_mismatch_{}.txt'.format(self.testDetails.testresultdir, self.chip_num, self.phy_rev, self.operation, reg_set, self.file_suffix)
                            else:
                                csv_files[reg_set] = '{}\{}_{}_{}_{}_mismatch_{}.csv'.format(self.testDetails.testresultdir, self.chip_num, self.phy_rev, self.operation, reg_set, self.run_time.replace(':', '.'))
                                mismatch_files[reg_set] = '{}\{}_{}_{}_{}_mismatch_{}.txt'.format(self.testDetails.testresultdir, self.chip_num, self.phy_rev, self.operation, reg_set, self.run_time.replace(':', '.'))
        
                            csv_output_string_list[reg_set] = []
                            output_string_list[reg_set] = []
                            
                            # First strings in mismatch file are wl ver.
                            for line in self.wl_ver.splitlines():
                                 output_string_list[reg_set].append(line)
                                 
                            output_string_list[reg_set].append("SVN script revision: %s" % __version__)
                            output_string_list[reg_set].append("SVN reference revision: %s\n" % self.desired_svn_ref_rev)

#            print csv_files
#            print mismatch_files

            # For each register set build up a long output string then write it to it's mismatch file.
            # Append it's mismatches to the output list of strings.
            # Each register set's output list of strings (if any) will be written to it's own mismatch file.
            for reg_set in mismatch_files: 
                output_string_list[reg_set].append('reg_set: {}'.format(reg_set))
                # For each test append mismatches in each chanspec.
                for mismatch_key in sorted(self.mismatch_info): # mismatch_key could be like; compare, test1, test2...
#                    print self.mismatch_info[mismatch_key][reg_set]
                    output_string_list[reg_set].append(mismatch_key + ':') # Put test name in.
                    # For each chanspec get the mismatches at that chanspec.
                    for chanspec in sorted(self.mismatch_info[mismatch_key][reg_set]):
                        # If mismatches at this chanspec print the chanspec, don't print chanspecs without mismatches.
                        if self.mismatch_info[mismatch_key][reg_set][chanspec]:
#                            print self.mismatch_info[mismatch_key][reg_set][chanspec]
                            output_string_list[reg_set].append("Chanspec: %s" % chanspec) # Only print if there are mismatches for this test/reg_set/chanspec.
                            if reg_set in ['phytable', 'phytbl', 'phytbl1']:
#                                print self.mismatch_info[mismatch_key][reg_set][chanspec]['unique_table_ids']
                                for source in ['ref', 'chip']:
                                    self.mismatch_info[mismatch_key][reg_set][chanspec]['unique_table_ids'][source]
                                    # Print unique table ids (list) if there are any.
#                                    if source in self.mismatch_info[mismatch_key][reg_set][chanspec]['unique_table_ids']:
                                    if any([table_id_list != [] for table_id_list in self.mismatch_info[mismatch_key][reg_set][chanspec]['unique_table_ids'][source]]):
                                        temp_str = "Unique %s table ids:" % source
                                        output_string_list[reg_set].append(temp_str)
                                        for table_id in sorted(self.mismatch_info[mismatch_key][reg_set][chanspec]['unique_table_ids'][source]):
                                            table_id = hex(table_id) + ':' 
                                            output_string_list[reg_set].append(table_id)
                                        output_string_list[reg_set].append('')
                                
                                    # Unique offsets (list) within common tables, if any list not empty, values are lists.
            #                        print "Number of unique phytable %s offsets: %s" % \
        #                            (source, len([offset_list for offset_list in self.mismatch_info[mismatch_key][reg_set][chanspec]['unique_offsets'][source].itervalues() if offset_list != []]))
                                    if any([offset_list != [] for offset_list in self.mismatch_info[mismatch_key][reg_set][chanspec]['unique_offsets'][source].itervalues()]):
                                        temp_str = "Unique %s offsets within common table ids:\nTable id   offset:" % source
                                        output_string_list[reg_set].append(temp_str)
                                        for table_id, offset_list in self.mismatch_info[mismatch_key][reg_set][chanspec]['unique_offsets'][source].iteritems():
                                            for offset in offset_list:
                                                temp_str = "{0}:   {1}".format(hex(table_id), hex(offset))
                                                output_string_list[reg_set].append(temp_str)
                                        output_string_list[reg_set].append('')
                    
                                else:
                                    # Unique registers (list)
            #                        print "Number of unique %s %s registers: %s" % (reg_set, source, len(self.unique_regs[source]))
                                    if self.unique_regs[source]: 
                                        temp_str = "Unique %s %s registers:" % (reg_set, source)
                                        output_string_list[reg_set].append(temp_str)
                        
                                        for reg in sorted([reg for reg in self.unique_regs[source]]):
                                            if reg_set == 'pmureg':
                                                temp_str = '{} {}'.format(reg[0], reg[1])
                                            else:    
                                                temp_str = "{0:0>{1}x}".format(reg, 3)
                                            output_string_list[reg_set].append(temp_str)
                                        output_string_list[reg_set].append('')
                        
                            # Register mismatches
                            if len(self.mismatch_info[mismatch_key][reg_set][chanspec]['reg_mismatches']):       
                                count = 0
                                output_string_list[reg_set].append("Register mismatches:")
                                if reg_set in ['phytable', 'phytbl', 'phytbl1']:
                                    output_string_list[reg_set].append("table id:offset   ref_value   chip_value:")
                                    for table_id in [table_id for table_id in sorted([item for item in self.mismatch_info[mismatch_key][reg_set][chanspec]['reg_mismatches']])]:
                                        for offset in [offset for offset in sorted([item for item in self.mismatch_info[mismatch_key][reg_set][chanspec]['reg_mismatches'][table_id]])]:
                                            output_string_list[reg_set].append(' '.join(["0x{0:0{1}X}:0x{2:0{3}X} =".format(table_id, 2, offset, 4), 
                                                ' '.join(["0x{0:0{1}X}".format(value, 4) for value in self.mismatch_info[mismatch_key][reg_set][chanspec]['reg_mismatches'][table_id][offset]['ref']]), 
                                                ' '.join(["0x{0:0{1}X}".format(value, 4) for value in self.mismatch_info[mismatch_key][reg_set][chanspec]['reg_mismatches'][table_id][offset]['chip']])]))
                                            count += 1
                                    output_string_list[reg_set].append('')
                                elif reg_set == 'pmureg':
                                    output_string_list[reg_set].append("write_reg   read_reg   offset   ref_value   chip_value:")
                                    for regs in sorted([item for item in self.mismatch_info[mismatch_key][reg_set][chanspec]['reg_mismatches']]):
                                        write_reg = "{0:>0{1}}".format(regs[0], 5)
                                        read_reg = "{0:>0{1}}".format(regs[1], 5)
                                        for offset in sorted([item for item in self.mismatch_info[mismatch_key][reg_set][chanspec]['reg_mismatches'][regs]]):
                                            # Make two lists, one comma separated for csv file, one space separated for mismatch file.
                                            csv_out, out = map(lambda item: item.join([write_reg, read_reg, "{0:>#0{1}x}".format(offset, 3), 
                                                self.mismatch_info[mismatch_key][reg_set][chanspec]['reg_mismatches'][regs][offset]['ref'], 
                                                self.mismatch_info[mismatch_key][reg_set][chanspec]['reg_mismatches'][regs][offset]['chip']]), [',', ' '])
                                            csv_output_string_list[reg_set].append(csv_out)
                                            output_string_list[reg_set].append(out)
                                            count += 1
                                    output_string_list[reg_set].append('')
                                elif reg_set == 'pciephyreg':
                                    if 'PCIeControlReg' in self.mismatch_info[mismatch_key][reg_set][chanspec]['reg_mismatches']:
                                        output_string_list[reg_set].append("PCIeControlReg ref_value: %s chip_value: %s" % 
                                                          (self.mismatch_info[mismatch_key][reg_set][chanspec]['reg_mismatches']['PCIeControlReg']['regaddrs']['0x0']['ref'], 
                                                          self.mismatch_info[mismatch_key][reg_set][chanspec]['reg_mismatches']['PCIeControlReg']['regaddrs']['0x0']['chip']) 
                                                          )
                                        
                                    # All the registers sorted without 'PCIeControlReg'
                                    output_string_list[reg_set].append("blkaddr   selection   offset   ref_value   chip_value:")
                                    # Sort them (ints) then turn to hex strings, dictionary keys are integers for sorting.
                                    for blkaddr in sorted([item for item in 
                                        [item for item in self.mismatch_info[mismatch_key][reg_set][chanspec]['reg_mismatches'] if item != 'PCIeControlReg']]):
                                        for regaddr in sorted([item for item in 
                                            self.mismatch_info[mismatch_key][reg_set][chanspec]['reg_mismatches'][blkaddr]['regaddrs']]):
                                            output_string_list[reg_set].append(' '.join(["{0:>0{1}x}".format(blkaddr, 3), 
                                                self.mismatch_info[mismatch_key][reg_set][chanspec]['reg_mismatches'][blkaddr]['selection'], "{0:>0{1}x}".format(regaddr, 2), 
                                                self.mismatch_info[mismatch_key][reg_set][chanspec]['reg_mismatches'][blkaddr]['regaddrs'][regaddr]['ref'], 
                                                self.mismatch_info[mismatch_key][reg_set][chanspec]['reg_mismatches'][blkaddr]['regaddrs'][regaddr]['chip']]))
                                            count += 1
                                    output_string_list[reg_set].append('')
                                elif reg_set in ['phyreg', 'radioreg']:
                                    output_string_list[reg_set].append("register   ref_value   chip_value:")
            #                        print self.mismatch_info[mismatch_key][reg_set]
                                    for reg in sorted([item for item in self.mismatch_info[mismatch_key][reg_set][chanspec]['reg_mismatches']]):
                                        try:
                                            print self.reg_names[reg_set][reg]
                                            reg_name = self.reg_names[reg_set][reg]
                                        except KeyError as e:
                                            print e
                                            reg_name = '' # No name for this register, set it empty.
                                        print 'register name: {}'.format(reg_name)                             
                                        output_string_list[reg_set].append("{0:>0{1}x}   {2}   {3} {4}".format(reg, 3, ' '.join(self.mismatch_info[mismatch_key][reg_set][chanspec]['reg_mismatches'][reg]['ref']), 
                                                                                          ' '.join(self.mismatch_info[mismatch_key][reg_set][chanspec]['reg_mismatches'][reg]['chip']), reg_name))                                    
                                        count += 1
                                    output_string_list[reg_set].append('')

#                print self.mismatch_info[mismatch_key][reg_set]
                
                print 'Mismatches found, saving {} mismatch info to {}'.format(reg_set, mismatch_files[reg_set])
                csv_output_str = '\n'.join([line for line in set(csv_output_string_list[reg_set])]) # Join list of string into one big long string.
                output_str = '\n'.join([line for line in output_string_list[reg_set]]) # Join list of string into one big long string.
        
                if self.verbosity > 0:
                    print output_str # Output string may be too big for mfgc's 4096 byte buffer.
                        
                # Each register set's output list of strings (if any) will be written to it's own mismatch file.
                # Write wl ver and output string to mismatch file.
                try:
                    mismatch_file = mismatch_files[reg_set]
                    with open(mismatch_file, 'w') as mf:
                        print "Opening %s for write" % mismatch_file
                        mf.write(output_str + '\n')
                        time.sleep(2) # Give time to close file
                        
                    # Create csv file for html report.    
                    print 'Creating {} CSV file {}:'.format(reg_set, csv_files[reg_set])
                    self.create_csv_file(csv_files[reg_set], csv_output_str) # Pass in filename for this register set and output string.
                except IOError as e:
                    print e
                    raise                            
        else:
            print 'No register mismatches found.'                                    
            return False
            
    def print_test_summary(self):
        # Print test results.
        print '.'
        print "Test Results Summary:"
        print 'Chip: {}'.format(self.chip_num)
        print "Driver/Firmware:"
        print self.wl_ver
        print ' '
        print 'Global loops: {}'.format(self.global_loops)
        
        num_pass_fail = {} 
        total_tests = int(self.total_test_loops) * len(self.chanspecs) * int(self.global_loops)   
        print 'total_tests: {}'.format(total_tests)
        
        status_list = [] # Holds counts pass/fail to see which one is the widest (most characters).
        # Sum the status counts for all tests on each chanspec to a list to find the widest one for chanspec column width later.
        for testname in sorted([testname for testname in self.operation_info[self.operation]]):
            num_pass_fail[testname] = {} 
            for chanspec in sorted([chanspec for chanspec in self.operation_info[self.operation][testname]]):
                num_pass_fail[testname][chanspec] = {'total_pass': 0, 'total_fail': 0} 
                for gloop in self.operation_info[self.operation][testname][chanspec]:
                    # How many Passes for all the local loops.
                    num_pass_local_loops = len([loop for loop in self.operation_info[self.operation][testname][chanspec][gloop] if self.operation_info[self.operation][testname][chanspec][gloop][loop]['status'].lower() == 'pass'])
                    num_fail_local_loops = len([loop for loop in self.operation_info[self.operation][testname][chanspec][gloop] if self.operation_info[self.operation][testname][chanspec][gloop][loop]['status'].lower() == 'fail'])
                    num_pass_fail[testname][chanspec]['total_pass'] += num_pass_local_loops 
                    num_pass_fail[testname][chanspec]['total_fail'] += num_fail_local_loops 

        # Lists of Pass/Fail counts for each test/chanspec, find width of widest one for column width.
        pass_count_list = [str(num_pass_fail[testname][chanspec]['total_pass']) for chanspec in num_pass_fail[testname] for testname in num_pass_fail]
        fail_count_list = [str(num_pass_fail[testname][chanspec]['total_fail']) for chanspec in num_pass_fail[testname] for testname in num_pass_fail]
        
        total_pass = 0
        total_fail = 0
        max_pass_count_width = max(itertools.imap(len, pass_count_list)) # Find length of longest number of Passes.
        max_fail_count_width = max(itertools.imap(len, fail_count_list)) # Find length of longest number of Fails.
        max_status_count_width = max(max_pass_count_width, max_fail_count_width)
#        print 'max_pass_count_width: {}'.format(max_pass_count_width)
#        print 'max_fail_count_width: {}'.format(max_fail_count_width)
#        print 'max_status_count_width: {}'.format(max_status_count_width)
        max_chanspec_width = max(itertools.imap(len, self.chanspecs)) # Find length of longest chanspec.
        chanspec_col_width = int(max_status_count_width) + 5 # Must be big enough for number of passes or fails plus '/PASS' or '/FAIL'.
#        print 'chanspec_col_width: {}'.format(chanspec_col_width)

        # Column widths for testname and number of test loops.
        max_testname_len = max(itertools.imap(len, self.operation_info[self.operation])) # Find length of longest test name for first column width.

        max_testloops_len = max(itertools.imap(len, [str(loop) for loop in self.operation_info[self.operation][testname][chanspec][gloop] \
                                                      for gloop in self.operation_info[self.operation][testname][chanspec] \
                                                      for chanspec in self.operation_info[self.operation][testname] \
                                                      for testname in self.operation_info[self.operation]])) # Find length of longest loop count for Loops column width.        
        num_chanspecs = len(self.chanspecs)
        max_testname_testloops_width = max_testname_len + max_testloops_len + 1 # Plus 1 for the space in between testname and test loops.
        
        if max_testname_testloops_width < len('Test name, test loops:'):
            max_testname_testloops_width = len('Test name, test loops:') # Make column as big as string.
                      
        header_line = '{0:<{mtntl}}{1}{2}'.format('Test name, test loops:', '  ' * num_chanspecs, 'Status per chanspec', mtntl = max_testname_testloops_width)  # Blank spaces 
        chanspecs_line = '{0:<{mtntl}}     '.format('Chanspecs:', mtntl = max_testname_testloops_width)  # Blank spaces 

        # Append chanspecs we tested on to chanspecs_line.
        for chanspec in self.chanspecs:
            chanspecs_line += '{0:^{mcw}}  '.format(chanspec, mcw = max_chanspec_width)
            
#        print '1234567890123456789012345'
        print header_line
        print chanspecs_line

        # Print table of test names, number of pass/fail for each chanspec, for each test ran.
        # For each test print a row of Pass counts at each chanspec then another row of the Fail counts.
        for testname in sorted([testname for testname in self.operation_info[self.operation]]):
#            print testname
            # Print all the pass counts for each chanspec then all the fail counts on the next line.
            #  1234567890123456789012345 string is 22 characters long.
            # Test name, test loops:     
            # test1_pre_assoc         10, name (15) plus space plus test loops length (1) = 16, shorter than string.
            # test2_post_assoc_pm0     1, Max testname length, a space and max test loops length. 
            # test2_post_assoc_pm0 10000, name (19) plus space plus test loops length (5) = 25, longer than string.
            # max testname length mtll, Max testname length left justified, a space and max test loops length right justified. 
            # max_testname_testloops_width, Used for 
            
            # Start building line with testname and test loops. Append number of Passes for each chanspec. Make another line with number of Fails.
            line = '{0:<{mtnl}} {1:>{mtllw_mtnl}}  '.format(testname, self.config['TEST_LOOPS'][testname], mtnl = max_testname_len, mtllw_mtnl = max_testname_testloops_width - max_testname_len)

            # Sum up the total number of Passes for all loops per chanspec, append to line.
            for chanspec in sorted([chanspec for chanspec in self.operation_info[self.operation][testname]]):
                total_pass += num_pass_fail[testname][chanspec]['total_pass']
                line += '{0:>{ccw}}  '.format(str(num_pass_fail[testname][chanspec]['total_pass']) + ' Pass', ccw=chanspec_col_width) # Test name and counts.

            print line # Testname, test loops, number of Pass
            line = '{0:<{mtntl}}   '.format(' ', mtntl = max_testname_testloops_width) # Blank spaces start Fail line.

            # Sum up the total number of Fails for all loops per chanspec, append to line.
            for chanspec in sorted([chanspec for chanspec in self.operation_info[self.operation][testname]]):
                total_fail += num_pass_fail[testname][chanspec]['total_fail']
                line += '{0:>{ccw}}  '.format(str(num_pass_fail[testname][chanspec]['total_fail']) + ' Fail', ccw=chanspec_col_width) # Test name and loops.
            print line # Blank spaces under testname, nlank spaces under loops of Fail
            
            print '.'

        # Totals
        print "Total Pass: {}/{}".format(total_pass, total_tests)
        print "Total Fail: {}/{}".format(total_fail, total_tests)
        didnt_run = total_tests - (total_pass + total_fail)
        
        if didnt_run:
            print '{} test(s) didn\'t run for some reason.'.format(total_tests - (total_pass + total_fail))
      
        # Print out the fail info if any.
        if any([loop for loop in self.operation_info[self.operation][testname][chanspec][gloop] \
                    if self.operation_info[self.operation][testname][chanspec][gloop][loop]['status'].lower() == 'fail' \
                    for gloop in self.operation_info[self.operation][testname][chanspec] \
                    for chanspec in self.operation_info[self.operation][testname] \
                    for testname in self.operation_info[self.operation] 
                    ]
               ):

            print '.'
            print 'Fail info:'
            print 'Test name, chanspec, global loop, test loop, comment'
            
            # Print out fail comments.  Testname chanspec comment(s)      
            for testname in sorted(self.operation_info[self.operation]):
                for chanspec in sorted(self.operation_info[self.operation][testname]):
                    for gloop in sorted(self.operation_info[self.operation][testname][chanspec]):
                        for loop in self.operation_info[self.operation][testname][chanspec][gloop]:
                            if self.operation_info[self.operation][testname][chanspec][gloop][loop]['status'].lower() == 'fail':
                                line = '{0:<{mtnl}} {1:^{mcw}} {2} {3} {4}'.format(testname, chanspec, gloop, loop, self.operation_info[self.operation][testname][chanspec][gloop][loop]['comment'], mtnl=max_testname_len, mcw=max_chanspec_width)
                                print line
            print '.'

    def run_tests(self, band, chanspec, gloop):
        ''' Run tests set to True in config file. Loads firmware before every test. 
            If test passes do a compare.
            Tests return a tuple of status and fail message on fail.
        '''
        
        a_test_failed = False
        have_data = False
        
        # If we don't have reference data for this chanspec, no sense running the test.
        for reg_set in self.reg_sets:                  
#            print self.data['ref'][reg_set]
            # See if there is any data for any register set for this chanspec or 'all'.  
            if any(k in self.data['ref'][reg_set] for k in (chanspec, 'all')):   
                have_data = True
                self.reg_sets[reg_set]['have_data'] = True # Have data for this register set.
                print 'Have ref data for {}.'.format(reg_set)
        
        # Run all tests on the band/chanspec passed in.
        if have_data:
            try:
                # If have ref data for any register set run the tests.         
                # For each testname run it for it's number of loops.    
                for testname in sorted(self.operation_info[self.operation]):
                    methodToCall = getattr(self, testname) # The name in the config file
                    # Run each test for the number of loops in the config file.
                    # Tests with 0 loop count won't come in here.
                    for loop in range(int(self.config['TEST_LOOPS'][testname])):
                        loop += 1 # range() starts at 0.
                        print "-- Running %s, band: %s, chanspec: %s, test loop %s/%s, global loop %s/%s --" % \
                        (testname, band, chanspec, loop, self.config['TEST_LOOPS'][testname], gloop, self.global_loops)
                        
                        if self.mode == 'dongle':
                            time.sleep(2)
                            self.load_driver() 
                            if self.load_firmware():
                                self.operation_info[self.operation][testname][chanspec][gloop][loop]['status'] = 'Fail'
                                self.operation_info[self.operation][testname][chanspec][gloop][loop]['comment'] = 'Load firmware failed.'                                
                                continue # Continue to next loop.
                        else:
                            ret, output = self.DUT.issuecmd(self.wl_prefix + 'ver') # Nic mode like Macs.
    
                        # Run the test method, the name in the config file
                        # Tests return a tuple of (status, comment), fail code and a comment on fail, no comment on Pass like:
                        # ('Pass', '') or ('Fail', 'Some fail comment here')
                        status, comment = methodToCall(testname, band, chanspec, gloop, loop)
                        print "status: %s" % status
                        print "comment: %s" % comment
                        self.operation_info[self.operation][testname][chanspec][gloop][loop]['status'] = status
                        self.operation_info[self.operation][testname][chanspec][gloop][loop]['comment'] = comment
                        
                        if status.lower() == 'fail':
#                            print "status: %s" % status
#                            print "output: %s" % output
#                            # Record the fail message for this test, chanspec, gloop and loop.
#                            self.operation_info[self.operation][testname][chanspec][gloop][loop]['status'] = status
#                            self.operation_info[self.operation][testname][chanspec][gloop][loop]['comment'] = output
                            print self.operation_info[self.operation][testname][chanspec][gloop][loop]['comment']
                            print "Test %s error, not comparing" % testname
                            a_test_failed = True
                            continue # Test failed, no compare, continue to next test.
                        else:
                            # Test didn't fail, compare the data for each register set.
                            for reg_set in self.reg_sets:    
                                # If have data for this register set/chanspec do the compare.
                                if self.reg_sets[reg_set]['have_data']:              
                                    print "Get/compare %s data for chanspec %s" % (reg_set, chanspec) # No test error
                                    if self.get_chip_data(reg_set, chanspec): # Get chip data into dictionaries using ignore list to filter  
                                        comment = 'Failed to get chip data for {} chanspec: {}'.format(reg_set, chanspec)
                                        print comment
                                        self.operation_info[self.operation][testname][chanspec][gloop][loop]['status'] = 'Fail'
                                        self.operation_info[self.operation][testname][chanspec][gloop][loop]['comment'] = comment
                                        a_test_failed = True
                                        continue # If fail to get data continue to next register set.
                                    # Compare data for this register set. Another register set may have already failed at this test/chanspec.
                                    if self.compare_data(testname, reg_set, chanspec): # Saves mismatches by chanspec to self.mismatch_info[mismatch_key]
                                        print 'Compare fail'
                                        # If 'Compare fail' in the comment for this test/chanspec (a previous fail comment exists from a previous loop or register set).
                                        if 'Compare fail' in self.operation_info[self.operation][testname][chanspec][gloop][loop]['comment']:
                                            # There is already a Compare fail comment, tack the register set on. 
                                            if reg_set not in self.operation_info[self.operation][testname][chanspec][gloop][loop]['comment']: # Append another register set.
                                                self.operation_info[self.operation][testname][chanspec][gloop][loop]['comment'] += ", %s" % reg_set
                                        else:
                                            # First comment, replace the empty comment with this comment.
                                            self.operation_info[self.operation][testname][chanspec][gloop][loop]['comment'] = "Compare fail %s" % reg_set # Replace the empty one.
                                        self.operation_info[self.operation][testname][chanspec][gloop][loop]['status'] = 'Fail'
    #                                    print self.operation_info[self.operation][testname][chanspec][gloop][loop]['comment']
                                        a_test_failed = True
                                    else:
                                        # Not a fail but, if it failed before on another register set leave it as a fail. If not Fail it must be N/A or Pass
                                        if self.operation_info[self.operation][testname][chanspec][gloop][loop]['status'].lower() != 'fail':
                                            self.operation_info[self.operation][testname][chanspec][gloop][loop]['status'] = 'Pass'
                            self.operation_info[self.operation][testname][chanspec][gloop][loop]['completed'] = True
#                            print "completed loops for %s %s: %s" % (testname, chanspec, self.operation_info[self.operation][testname][chanspec][gloop][loop]['completed_loops'])
#            except (AttributeError, KeyError, ValueError) as e:
            except (KeyboardInterrupt, SystemExit):
                raise
            except:
                (frame, filename, line_number, function_name, lines, index) = inspect.getouterframes(inspect.currentframe())[1]
                print "Unexpected error in %s." % function_name
                traceback.print_exc(file=sys.stdout)
                return True  
        else:
            print "No %s reference data for chanspec %s, skipping test(s)." % (reg_set, chanspec)
            return False
        print 
        
        # All tests done.
        if a_test_failed:
            return True
        else:
            return False
        
    def send_mdio_commands(self, blkaddr, regaddr):
        ''' '''
            
        cmd = {'nic': self.wl_prefix + 'pcieserdesreg',
               'dongle': 'dhd -i eth1 pciecorereg'}
        
        command_string = ''
        
        if self.mode == 'dongle':
            command_string += cmd[self.mode] + ' 0x128 0x1f02' + ' ;'
            command_string += cmd[self.mode] + ' 0x12c 0x8000' + blkaddr + '0' + ' ;'
            command_string += cmd[self.mode] + '0x128 0x2000' + regaddr + '02' + ' ;'
            command_string += cmd[self.mode] + ' 0x130' + ' ;'
            command_string += cmd[self.mode] + ' 0x' + blkaddr + ' 0x' + regaddr + ' ;'
            
            ret, output = self.DUT.issuecmd(cmd[self.mode] + ' 0x128 0x1f02')
            ret, output = self.DUT.issuecmd(cmd[self.mode] + ' 0x12c 0x8000' + blkaddr + '0')
    #                time.sleep(.5)
    #                self.DUT.issuecmd(cmd[self.mode] + ' 0x12c')
            
            ret, output = self.DUT.issuecmd(cmd[self.mode] + ' 0x128 0x2000' + regaddr + '02')
    #                time.sleep(.1)
            ret, output = self.DUT.issuecmd(cmd[self.mode] + ' 0x130')
        elif self.mode == 'nic':
            ret, output = self.DUT.issuecmd(cmd[self.mode] + ' 0x' + blkaddr + ' 0x' + regaddr)
            
        return ret, output
        
    def send_telnet_command(self, cmd, search_string, timeout=10):
        ''' Create telnet session, send telnet command, return output data, close telnet session. '''
        
        ret = 0
        output = ''
            
        if self.verbosity > 0:
            print "Creating telnet object for %s" % self.ap_ip
            
        try:
            self.telnet_session = telnetlib.Telnet(self.ap_ip, timeout=10)
            if self.verbosity > 1:
                print "Issue telnet cmd to %s: %s" % (self.ap_ip, cmd)
            self.telnet_session.read_until('#')
            self.telnet_session.write(cmd)
            time.sleep(2)
            output = self.telnet_session.read_until(search_string, timeout)
            if self.verbosity > 0:
                print 'Closing telnet object.'
            self.telnet_session.close()
        except IOError as e:
            print e
            ret = True
        
        if self.verbosity > 1:
            print "return code: %s" % ret
            print "output: \n%s" % output

        return (ret, output)
        
    def set_associate_ap(self, band, chanspec, SSID):
        ''' Set access point band/chanspec then associate to it. 
            1. Join AP.
            2. Set chanspec.
            3. Join again on new chanspec.
        
        '''
        
        # Set band/chanspec on AP then dissassociate and reassociate on to the new chanspec.
        if self.set_ap_band_chanspec(band, chanspec):
            print "Setting access point to chanspec %s failed" % chanspec
            return True
        else: # Setting band and chanspec worked (probably got disconnected), now associate to it if chanspec got set.
            if self.associate_ap(self.SSID[self.ap_type][band]):
                print 'Associate failed'
                return True
            else:
                return False
    
    def set_ap_band_chanspec(self, band, chanspec):
        ''' Set the band/chanspec on the access point. 
        
            For soft AP run bandchan.sh on the AP.
            For hard AP associate to 2G or 5G side.
            Send wl commands to -i eth1 for 2G, -i eth2 for 5G.
        '''
        
        band_intf = {'a': 'eth2', 'b': 'eth1'} # 5G, a eth2, 2G, b, eth1
        
        # Set band and chanspec on hard or soft access point.
        if self.ap_type == 'soft':
            # Set chanspec on soft AP, run shell script on AP passing band and chanspec in to script as parameters.
            print "Setting band/chanspec on access point to: %s %s" % (band, chanspec)
            if self.ap_os == 'linux':
                ret, output = self.DUT.issuecmd('rsh -lroot ' + self.ap_ip + ' /opt/bandchan.sh %s %s %s' % (band, chanspec, self.SSID[self.ap_type][band]))
                if ret:
                    print "return: %s" % ret
                    return True
                elif output in ['', -1, self.ap_ip + ': No route to host']:
                    print 'output: {}'.format(output)
                    return True
                else:
                    return False
            elif self.ap_os == 'windows':
                ret, output = self.DUT.issuecmd('rsh ' + self.ap_ip + ' start cmd /c c:\\bandchan.cmd %s %s %s' % (band, chanspec, self.SSID[self.ap_type][band]))
                if ret:
                    print "return: %s" % ret
                    return True
                else:
                    return False
        else:
            # Join band, set chanspec on hard AP.
            print "Joining access point: %s SSID: %s (band %s)" % (self.ap_ip, self.SSID[self.ap_type][band], band)
            
            # Try to associate to the SSID name for that band.
            if self.associate_ap(self.SSID[self.ap_type][band]):
                print 'Failed to associate.'
                return True 
        
            print "Setting AP chanspec: %s" % chanspec
            cmd = "wl -i %s chanspec %s\n" % (band_intf[band], chanspec)
            ret, output = self.send_telnet_command(cmd, '#') # Command and search string.

            if ret:
                print "return: %s" % ret
                return True
            
            if 'Bad' in output:
                return True
            
            # Check that chanspec got set.
            cmd = 'wl -i {} chanspec\n'.format(band_intf[band])
            ret, output = self.send_telnet_command(cmd, '#') # Command and search string.
            
            if ret:
                print "return: %s" % ret
                return True
            else:
                ap_chanspec = output.splitlines()[1].split()[0].strip()
                print 'ap chanspec: {}'.format(ap_chanspec)
                if ap_chanspec != chanspec:
                    print 'Failed to set AP chanspec.'
                    return True 
            
            return False
                
    def set_chip_band(self, band):
        ''' Set the local band on the DUT. '''
        
        print "Setting chip band %s" % band

        ret, output = self.DUT.issuecmd(self.wl_prefix + 'band ' + band, True) # Change local DUT band, True = quit on error.
        if ret:
#            print ret
            return ret
        else:
            # Check if band got set.
            cmd = self.wl_prefix + "band"
            ret, output = self.DUT.issuecmd(cmd)
                        
            if ret:
                print ret
                return ret
            else:
                current_band = output.split()[0] 

            if current_band != band:
                return "Band %s didn\'t get set." % band
            else:    
                return False
    
    def set_chip_chanspec(self, chanspec):
        ''' Set the local chip chanspec on the DUT. '''
        
        print "Setting chip chanspec %s" % chanspec

        # Set local chip chanspec
        cmd = self.wl_prefix + "chanspec %s" % chanspec
        ret, output = self.DUT.issuecmd(cmd)
        if ret:
            print "ret: %s" % ret
            return ret
        elif not output.startswith('Chanspec set to'):
            print "output: %s" % output
            return output
        else:
            chanspec_set = output.split()[0]
            print "chanspec_set output: %s" % chanspec_set
            
        # Send rest of commands.
        for cmd in [self.wl_prefix + 'mpc 0',
#                    self.wl_prefix + 'txchain 3',
#                    self.wl_prefix + 'rxchain 3',
                    'sleep 2',
                    self.wl_prefix + 'up',
                    self.wl_prefix + 'phy_forcecal 1',
                    ]:

            ret, output = self.DUT.issuecmd(cmd)
                        
            if ret:
                print ret
                return ret
        else:
            # Check if chanspec got set.
            cmd = self.wl_prefix + "chanspec"
            ret, output = self.DUT.issuecmd(cmd)
                        
            if ret:
                print ret
                return ret
            else:
                current_chanspec = output.split()[0] 

            if current_chanspec != chanspec:
                return "Chanspec %s didn\'t get set." % chanspec
            else:    
                return False
    
    def start_iperf_client(self):
        ''' Starts iPerf running on client. '''
        
        try:
            iperf_cmd = 'iperf -c {} -B{} -fm -w2m -i1 -l4k -p20006 -t10'.format(self.iperf_server_ip, self.dut_wl_ip)
            print "Starting iPerf client"
            ret, output = self.DUT.issuecmd(iperf_cmd, session = 'iperf_client')
    
            if ret:
                print "Starting iPerf client failed"
                print ret
                return ret
            elif 'Connection refused' in output:
                print output
                return True
            else:
                print "iPerf output: %s" % output
                return False
        except OSError as e:
            print e
#            return 1
            raise

    def start_iperf_server(self):
        ''' Process function to start iPerf on the iPerf server. '''
        
        iperf_cmd = 'iperf -B{} -s -fm -w2m -i1 -l4k -p20006'.format(self.iperf_server_ip)
        print 'Starting iPerf server on {}'.format(self.iperf_server_ip)
        
        if self.ap_type == 'hard':
            ret, output = self.CONTROLLER.issuecmd(iperf_cmd, session = 'iperf_server')
        elif self.ap_type == 'soft':
            ret, output = self.REF.issuecmd(iperf_cmd, session = 'iperf_server')
            

        if ret:
            print "Starting iPerf server failed"
            print ret
            return ret
        else:
#            print output
#            print "iPerf server started"
#            time.sleep(3) # Give some time for the server to get started.

            return False
        
    def stop_iperf_server(self):
        ''' Stop iPerf on the iPerf server. '''
        
        print "Stopping iPerf server"
        output = ''
        
        # Check if iPerf already running
        if self.iperf_server_os == 'linux':
#            ret, output = self.DUT.issuecmd('ssh -lroot ' + self.iperf_server_ip + ' killall iperf')
            ret, output = self.REF.issuecmd('killall iperf')
            if ret or 'Permission denied' in output:
                return True
            else:
                print output
        elif self.iperf_server_os == 'windows':
#            ret, output = self.DUT.issuecmd('ssh -lroot ' + self.iperf_server_ip + ' TASKKILL /F /IM iperf.exe')
            ret, output = self.CONTROLLER.issuecmd('TASKKILL /F /IM iperf.exe')
            if ret:
                return True
            else:
                print output
        else:
            print 'Unknown operating system'
            sys.exit()
            
        return False
            
    def test1_pre_assoc(self, testname, band, chanspec, gloop, loop):
        ''' Dump and compare pre-association:
            Boot OS
            Load F/W  (no scan OR association )
            Issue wl ver
            Check for low current
            Dump phyregs, tables etc..
            Compare with the golden values
            
            Returns a tuple of status and fail message on fail.
        '''
        
        # Set local chip band/chanspec, we're just comparing unassociated.
        if self.set_chip_band(band): # Set local DUT band
#            return True # band didn't get set.
            return ('Fail', 'Band {} didn\'t get set'.format(band)) # band didn't get set.
        
        if self.set_chip_chanspec(chanspec): # Set local DUT chanspec, verifies that it got set.
            return ('Fail', 'Chanspec {} didn\'t get set'.format(chanspec)) # band didn't get set.
        
 #       if ret:
#            self.operation_info[self.operation][testname][chanspec][gloop][loop]['status'] = 'Fail'
#            self.operation_info[self.operation][testname][chanspec][gloop][loop]['comment'] = "Setting chip chanspec %s failed." % chanspec
#            print self.operation_info[self.operation][testname][chanspec][gloop][loop]['comment']
#            return True
#            return (ret, "Setting chip chanspec %s failed." % chanspec)
        else:
            return ('PASS', '') # 
    
    def test2_post_assoc_pm0(self, testname, band, chanspec, gloop, loop, pm_mode='0'):
        ''' Dump and compare after association ( PM0 mode)
                Scan and associate to an AP (infra mode) 
                5G, Channel xx
                Issue wl ver
                Wl PM 0
                Check for current (should be high, no DS cycle )
                Dump phyregs, tables etc..
                Compare with the golden values
    
                Variations :
                    Run this test in Different 5G channels
                    Run this test in different 2G channels
                    
                Cidre    Non-Cidre/Albarossa
                1/20        1/20
                36/20       2/20
                100/20      12/20
                149/20      36/20
                36/40       100/20
                44/40       149/20
                36/80       36/40
                100/80      44/40
                            36/80
                            100/80
                            
                Assumes AP is already set up.
        '''
        
        # Associate to access point if set in config file.
        if self.associate:
            if self.set_associate_ap(band, chanspec, self.SSID[self.ap_type][band]):
                return ('Fail', 'Failed setting access point chanspec and associating to it.'.format(band)) # Associate failed.
        else:
            return ('Fail', 'This test requires associating with access point.'.format(band)) # Associate failed.
        
        if self.set_chip_band(band): # Set band after associate so we can dump registers.
            return ('Fail', 'Band {} didn\'t get set'.format(band)) # band didn't get set.
            
        print "Setting PM%s" % pm_mode
        ret, output = self.DUT.issuecmd(self.wl_prefix + 'PM ' + pm_mode)
        
        if ret:
#            return ret
            return ('Fail', 'Setting PM {} failed.'.format(pm_mode)) # 
        else:
            return ('PASS', '') # 
                          
    def test3_post_assoc_pm1(self, testname, band, chanspec, gloop, loop):
        ''' Dump and compare after association ( PM1 mode)        
                Boot OS
                Load F/W 
                Scan and associate to an AP (infra mode) 
                5G, Channel xx
                Issue wl ver
                Wl PM1
                Be idle for 2 sec
                Check low current (device should have gone in DS)
                Issue wl ver
                Dump phyregs, tables etc..
                Compare with the golden values
                
                Variations :
                    Run this test in Different 5G channels
                    Run this test in different 2G channels
        '''

        pm_mode = '1'
        # Just like test2 with PM1
        return self.test2_post_assoc_pm0(testname, band, chanspec, gloop, loop, pm_mode)

    def test4_traffic_ds(self, testname, band, chanspec, gloop, loop):
        ''' Dump and compare after traffic and DS cycle
                Boot OS
                Load F/W 
                Scan and associate to an AP (infra mode) 
                5G, Channel xx
                Issue wl ver
                Wl PM 0
                Run iPerf for 10 sec
                Wl PM 2
                Be idle for 2 sec
                Check low current (device should have gone in DS)
                Issue wl ver
                Dump phyregs, tables etc..
                Compare with the golden values
    
                Variations :
                    Run this test in Different 5G channels
                    Run this test in different 2G channels
            
                iPerf server command: iperf -s -fm -w2m -i1 -l4k -p20006 -t10
                iPerf client command: iperf -c <access_point_ip> -fm -w2m -i1 -l4k -p20006 -t10
                
            Need two threads, one to start iPerf server, the other to run the client at same time.    
        '''
        
        process_found = False

        # Associate to access point if set in config file.
        if self.associate:
            if self.set_associate_ap(band, chanspec, self.SSID[self.ap_type][band]):
                return ('Fail', 'Failed setting access point chanspec and associating to it.'.format(band)) # Associate failed.
        else:
            return ('Fail', 'This test requires associating with access point.'.format(band)) # Associate failed.
        
        if self.set_chip_band(band): # Set band after associate so we can dump registers.
            return ('Fail', 'Band {} didn\'t get set'.format(band)) # band didn't get set.

        ret, output = self.DUT.issuecmd(self.wl_prefix + 'PM 0')
        
#        print 'Running iPerf'
        if self.stop_iperf_server(): # Stop any iPerf already running on the iPerf server.
            return ('Fail', 'Stopping iPerf server failed.')
        
        # Create new threads
        iperf_server_thread = myThread(1, "Thread-1-iperf_server", self.start_iperf_server)
        iperf_client_thread = myThread(2, "Thread-2-iperf_client", self.start_iperf_client)

        try:
            if iperf_server_thread.start():
                return ('Fail', 'Starting iPerf server failed.') 
            
            time.sleep(10) # Give some time for the server to get started.
            
            if iperf_client_thread.start():
                return ('Fail', 'Starting iPerf client failed.') 
            
            time.sleep(2) # Give some time for client to finish.
            iperf_client_thread.join() # Client back to main thread.
            iperf_server_thread.join() # Server back to main thread.
        except:
            (frame, filename, line_number, function_name, lines, index) = inspect.getouterframes(inspect.currentframe())[1]
            comment = 'Unexpected error in {}.'.format(function_name)
            traceback.print_exc(file=sys.stdout)
            return ('Fail', comment)
        
        ret, output = self.DUT.issuecmd(self.wl_prefix + 'PM 2')
        time.sleep(2)
        return ('PASS', '')
        
    def test5_d3_cold_unassoc(self, testname, band, chanspec, gloop, loop):
        ''' Dump and compare after D3 cold cycle - Un Associated
                Boot OS
                Load F/W 
                Issue wl ver
                Be idle for 2 sec
                Check low current 
                Issue wl ver
                Issue rtcwake command ( rtcwake -m s 45 )
                Check for low current 
                After wake, Check wl pwrstats for D3 count and PERST# assertion
                Dump phyregs, tables etc..
                Compare with the golden values
                
                
            Mac only (pmset):
            The -a, -b, -c, -u flags deter-mine determine whether the settings apply to battery ( -b ), charger (wall power) ( -c ), UPS ( -u ) or all ( -a).

            SAFE SLEEP ARGUMENTS
                 hibernatemode takes a bitfield argument defining SafeSleep behavior. Passing 0 disables SafeSleep alto-gether, altogether,
                 gether, forcing the computer into a regular sleep.
            
                 ____ ___1 (bit 0) enables hibernation; causes OS X to write memory state to hibernation image at sleep
                 time. On wake (without bit 1 set) OS X will resume from the hibernation image. Bit 0 set (without bit 1
                 set) causes OS X to write memory state and immediately hibernate at sleep time.
            
                 ____ __1_ (bit 1), in conjunction with bit 0, causes OS X to maintain system state in memory and leave
                 system power on until battery level drops below a near empty threshold (This enables quicker wakeup
                 from memory while battery power is available). Upon nearly emptying the battery, OS X shuts off all
                 system power and hibernates; on wake the system will resume from hibernation image, not from memory.
            
                 ____ 1___ (bit 3) encourages the dynamic pager to page out inactive pages prior to hibernation, for a
                 smaller memory footprint.
            
                 ___1 ____ (bit 4) encourages the dynamic pager to page out more aggressively prior to hibernation, for
                 a smaller memory footprint.
            
                 We do not recommend modifying hibernation settings. Any changes you make are not supported. If you
                 choose to do so anyway, we recommend using one of these three settings. For your sake and mine, please
                 don't use anything other 0, 3, or 25.
            
                 hibernatemode = 0 (binary 0000) by default on supported desktops. The system will not back memory up to
                 persistent storage. The system must wake from the contents of memory; the system will lose context on
                 power loss. This is, historically, plain old sleep.
            
                 hibernatemode = 3 (binary 0011) by default on supported portables. The system will store a copy of mem-ory memory
                 ory to persistent storage (the disk), and will power memory during sleep. The system will wake from
                 memory, unless a power loss forces it to restore from disk image.
            
                 hibernatemode = 25 (binary 0001 1001) is only settable via pmset. The system will store a copy of mem-ory memory
                 ory to persistent storage (the disk), and will remove power to memory. The system will restore from
                 disk image. If you want "hibernation" - slower sleeps, slower wakes, and better battery life, you
                 should use this setting.
            
                 Please note that hibernatefile may only point to a file located on the root volume.                
                
        '''  
        
        # Set local chip chanspec, we're just comparing unassociated.
        if self.set_chip_chanspec(chanspec): # Set local DUT chanspec
#            return True # chanspec didn't get set, try next one.
            return ('Fail', 'Chanspec {} didn\'t get set'.format(chanspec)) # band didn't get set.

        if self.set_chip_band(band): # Set band after associate so we can dump registers.
            return ('Fail', 'Band {} didn\'t get set'.format(band)) # band didn't get set.

        print 'Getting wl pwrstats'
        wl_pwrstats_pcie = self.get_wl_pwrstats_pcie() # Returns a dictionary on success or True if fail.
        
        if type(wl_pwrstats_pcie) == dict:
#            print wl_pwrstats_pcie
            before_l2_cnt = int(wl_pwrstats_pcie['l2']['cnt'])
        else:
            print wl_pwrstats_pcie
            return ('Fail', 'Error getting wl pwrstats before rtcwake.') # band didn't get set.
        
        print "Putting system in low power state for %s secs...." % self.operation_info[self.operation][testname][chanspec][gloop][loop]['rtcwake_time']
        
        # Put hosts system to sleep.
        if self.mode == 'dongle':
            ret, output = self.DUT.issuecmd("rtcwake -m mem -s %s" % self.operation_info[self.operation][testname][chanspec][gloop][loop]['rtcwake_time'])
        elif self.mode == 'nic':
            ret, output = self.DUT.issuecmd('pmset -a hibernatemode 3') 
            ret, output = self.DUT.issuecmd('pmset repeat cancel')
            # check the present system time; calculate new time 
            wake_time = '\"' + (datetime.datetime.now() + datetime.timedelta(seconds=self.operation_info[self.operation][testname][chanspec][gloop][loop]['rtcwake_time'])).strftime("%m/%d/%y %H:%M:%S") + '\"' # Must be quoted
            ret, output = self.DUT.issuecmd("pmset schedule wake %s" % wake_time)
            ret, output = self.DUT.issuecmd('shutdown -s now')
            
            time.sleep(self.rtcwake_time[testname] + 5) # Stay here until it wakes up.
        
        if ret:
            print "ret: %s" % ret
            print "output: %s" % output
            return ('Fail', output) # band didn't get set.
            
        print 'Getting wl pwrstats'
        wl_pwrstats_pcie = self.get_wl_pwrstats_pcie() # Returns a dictionary on success or True if fail.
#        print type(wl_pwrstats_pcie)
#        print wl_pwrstats_pcie
#        print len(wl_pwrstats_pcie)
        
        if type(wl_pwrstats_pcie) == dict and len(wl_pwrstats_pcie) != 0:
#            print wl_pwrstats_pcie
            after_l2_cnt = int(wl_pwrstats_pcie['l2']['cnt'])
        else:
            print wl_pwrstats_pcie
            return ('Fail', 'Error getting wl pwrstats after rtcwake.') #
        
        print "l2 count before sleep: %s" % before_l2_cnt
        print "l2 count after sleep: %s" % after_l2_cnt
        
        if after_l2_cnt <= before_l2_cnt:
            print ' '
            print "***** l2 count didn't increase, device didn't go into deep sleep! *****"
            print ' '
#            return True
            return ('Fail', 'l2 count didn\'t increase.') #
        
        return ('PASS', '') # 
        
    def test6_d3_cold_assoc(self, testname, band, chanspec, gloop, loop):
        ''' Dump and compare after D3 cold cycle - Associated
                Boot OS
                Load F/W 
                Scan and associate to an AP (infra mode) 
                5G, Channel xx
                Issue wl ver
                Wl PM 2
                Be idle for 2 sec
                Check low current (device should have gone in DS)
                Issue rtcwake command ( rtcwake -m s 45 )
                Check for low current 
                After wake, Check wl pwrstats for D3 count and PERST# assertion
                Dump phyregs, tables etc..
                Compare with the golden values
                
                
                Variations :
                    Run this test in Different 5G channels
                    Run this test in different 2G channels
                    
            Same as test 6 except associated.
        '''
        
        # Associate to access point if set in config file.
        if self.associate:
            if self.set_associate_ap(band, chanspec, self.SSID[self.ap_type][band]):
                return ('Fail', 'Failed setting access point chanspec and associating to it.'.format(band)) # Associate failed.
        else:
            return ('Fail', 'This test requires associating with access point.'.format(band)) # Associate failed.
        
        if self.set_chip_band(band): # Set band after associate so we can dump registers.
            return ('Fail', 'Band {} didn\'t get set'.format(band)) # band didn't get set.

        ret, output = self.DUT.issuecmd(self.wl_prefix + 'PM 2')
        time.sleep(2)
        
        print 'Getting wl pwrstats'
        wl_pwrstats_pcie = self.get_wl_pwrstats_pcie() # Returns a dictionary on success or True if fail.
        
        if type(wl_pwrstats_pcie) == dict and len(wl_pwrstats_pcie) != 0:
#            print wl_pwrstats_pcie
            before_l2_cnt = int(wl_pwrstats_pcie['l2']['cnt'])
            print "l2 count before sleep: %s" % before_l2_cnt
        else:
            return ('Fail', 'Error getting wl pwrstats.') #
        
        print "Putting system in low power state for %s secs...." % self.operation_info[self.operation][testname][chanspec][gloop][loop]['rtcwake_time']
        
        # Put hosts system to sleep.
        if self.mode == 'dongle':
            pass
            ret, output = self.DUT.issuecmd("rtcwake -m mem -s %s" % self.operation_info[self.operation][testname][chanspec][gloop][loop]['rtcwake_time'])
        elif self.mode == 'nic':
            ret, output = self.DUT.issuecmd('pmset -a hibernatemode 3') 
            ret, output = self.DUT.issuecmd('pmset repeat cancel')
            # check the present system time; calculate new time 
            # pmset schedule wake '08/04/15 20:13:45'
            print str(datetime.datetime.now()).split('.')[0]
            wake_time = '\"' + (datetime.datetime.now() + datetime.timedelta(seconds=self.operation_info[self.operation][testname][chanspec][gloop][loop]['rtcwake_time'])).strftime("%m/%d/%y %H:%M:%S") + '\"'
            ret, output = self.DUT.issuecmd("pmset schedule wake %s" % wake_time)
            ret, output = self.DUT.issuecmd('shutdown -s now')
                            
            time.sleep(self.rtcwake_time[testname] + 5) # Stay here until it wakes up.
        
        if ret:
            print "output: %s" % output
            return ('Fail', output) # band didn't get set.
            
        print 'Getting wl pwrstats'
        wl_pwrstats_pcie = self.get_wl_pwrstats_pcie() # Returns a dictionary on success or True if fail.
        
        try:
            if type(wl_pwrstats_pcie) == dict and len(wl_pwrstats_pcie) != 0:
    #            print wl_pwrstats_pcie
                after_l2_cnt = int(wl_pwrstats_pcie['l2']['cnt'])
                print "l2 count after sleep: %s" % after_l2_cnt
            else:
                print 'Error getting wl pwrstats, test aborted.'
                return True
        except KeyError as e:
            print e
            print wl_pwrstats_pcie
        
        print "l2 count before sleep: %s" % before_l2_cnt
        print "l2 count after sleep: %s" % after_l2_cnt
                
        if after_l2_cnt <= before_l2_cnt:
            print ' '
            print "***** l2 count didn't increase, device didn't go into deep sleep! *****"
            print ' '
            return ('Fail', 'l2 count didn\'t increase.') #
        
        return ('PASS', '') # 
        
    def testRun(self):
        ''' The main function, like main() in a normal program.
        
            Do the operation on each chanspec.
        
        '''
                
#        Commented out due to too many conflicting svn versions.
#        if self.check_svn_versions(): # Make sure DUT has the latest svn script and reference files.
#            return 1

        # Perform the operation on each chanspec.
        if self.operation == 'loadfw':
            return 0 # Load firmware already done in __init__().
        elif self.operation in ['dump']:
            self.global_loops = 1
            
            # Dictionary to store info about dump operations.
            self.operation_info[self.operation] = {} 
            for chanspec in self.chanspecs:
                self.operation_info[self.operation][chanspec] = {'comment': '', 'status': 'N/A'}
            
            # Set up dump files and dumped flags.
            try:
                for reg_set in self.reg_sets:
                    self.reg_sets[reg_set]['dumped'] = False # Bool flag for later.
                    
                    # If filename specified on command line dump to it, else dump to default name.
                    if hasattr(self, 'file_suffix'):
                        self.reg_sets[reg_set]['dump_file'] = "%s\%s_%s_%s_%s_%s.txt" % (self.testDetails.testresultdir, self.chip_num, self.phy_rev, self.program, reg_set, self.file_suffix)
                    else:
                        self.reg_sets[reg_set]['dump_file'] = "%s\%s_%s_%s_%s_%s.txt" % (self.testDetails.testresultdir, self.chip_num, self.phy_rev, self.program, reg_set, self.run_time.replace(':', '.'))
                

                    # Put wl ver info at the top of the output files. Open for write to delete any old one, append new values later.
                    with open(self.reg_sets[reg_set]['dump_file'], 'w') as df:
                        print "Opening %s for write" % self.reg_sets[reg_set]['dump_file']
                        for line in self.wl_ver.splitlines():
                            df.write('# ' + line + '\n')
            except IOError as e:
                    print e
        elif self.operation in ['compare', 'test']:
            # Golden reference files needed for compare or test.
            print 'Get ref data'
            
#            print self.reg_sets
            for reg_set in self.reg_sets:
                self.get_ref_data(reg_set) # Read in golden reference values into local dictionary. 
        else:
            print "Invalid operation: %s" % self.operation
            return 1

        # -s = output filename suffix.
        self.results_dir = self.testDetails.testresultdir.split(os.sep)[-1] # Split by path separator, take the last one.
        date_time = self.results_dir.split('_', 1)[1] # Split by first underscore to remove test name, get timestamp.
        destFolder = self.testDetails.testresultdir
        
        a_test_failed = False
    
        # Loop through all chanspecs, perform the operation on each chanspec.
        try:
            # Global loop, repeat the operation this many times.
            for gloop in range(1, int(self.global_loops) + 1):
                print "gloop: %s" % gloop
                # Operate on each chanspec.
                for chanspec in sorted(self.chanspecs):
#                        print "self.chanspecs: %s" % self.chanspecs
                    print "chanspec: %s" % chanspec
                    chanspec_num = int("".join(itertools.takewhile(str.isdigit, chanspec))) # Get chars up to first non-digit.                                   

                    # Determine band from chanspec number.
                    if int(chanspec_num) < 30:
                        band = 'b'
                    else:
                        band = 'a'

                    print "band: %s" % band

                    # Dump always sets chanspec, compare only sets chanspec if it has data for it to compare.
                    if self.operation == 'dump': # Dump is always unassociated, or comparing unassociated.
                        if self.set_chip_band(band): # Set local DUT band
                            continue # band didn't get set, try next one.

#                    have_data = False                        
#                    if self.operation == 'dump': # 
                        if self.set_chip_chanspec(chanspec): # Set local DUT chanspec
                            continue # chanspec didn't get set, try next one.
                        else:
                            # Perform the operation on this chanspec. Dumps are unassociated.
                            if self.dump(chanspec): # Dump all register sets unassociated. 
                                return 1 # dump failed, exit with return code 1.
                    else:
                        # If operation is not dump must be loadfw, compare or test
                        # Check if there is reference data for this chanspec.
                        # If nothing to compare to, no sense setting chanspec.
                        have_data = False
                        print ' '
                        
                        # Check if any register sets have reference data.
                        for reg_set in self.data['ref']:
                            if any(k in self.data['ref'][reg_set] for k in (chanspec, 'all')) :
                                if self.verbosity > 0:
                                    print "Have %s reference values for chanspec %s" % (reg_set, chanspec)
                                have_data = True # A register set has data for this chanspec
#                                    break # We have data for one of the register sets, no sense checking any more. 
                            
                        # If we don't have reference data for any register set for this chanspec try next chanspec.
                        if not have_data:
                            if self.verbosity > 0:
                                print "No reference data for any register sets specified for chanspec %s, skipping." % chanspec
                            continue # Continue to next chanspec    
                        else:
                            # If we have data get the register names.
                            self.get_reg_names(reg_set, chanspec) 
                            # Tests will associate or not in each test.
                            if self.operation == 'compare':
                                print 'Doing compare'
                                if self.associate: # If config file says to do an associated compare
                                    self.set_ap_band_chanspec(band, chanspec) # Set chanspec on AP
                                    if self.associate_ap(self.SSID[self.ap_type][band], chanspec): # If associate fails try next chanspec.
                                        return 1 # Associate failed, exit program.
                                else: # Unassociated compare.
                                    if self.set_chip_chanspec(chanspec): # Set local DUT chanspec
                                        return 1 # chanspec didn't get set, exit program.

                                if self.compare(chanspec): # Perform the operation on this chanspec. 
                                    return 1 # Compare failed, exit program.
                            elif self.operation == 'test':
                                print "Running tests on band: %s chanspec: %s" % (band, chanspec)
                                self.data['chip'] = {} # Clear out old data from previous loop.
                                if self.run_tests(band, chanspec, gloop):
                                    print 'Fail'
                                    a_test_failed = True # A test failed.

#            if self.compare_performed:
#                ret = self.print_compare_summary()
#                if ret:
#                    return ret
#                else:
#                    if a_test_failed:
#                        return 1
#                    else:
#                        return 0
            
#        except (IOError, OSError) as e:
#            print str(e)
#            return 1
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            (frame, filename, line_number, function_name, lines, index) = inspect.getouterframes(inspect.currentframe())[1]
            print "Unexpected error in %s." % function_name
            traceback.print_exc(file=sys.stdout)
#            raise
        finally:
            try:
                self # Check for object, there may not be an object if there was an error or svn message.
            except NameError:
                pass
            else:
                if self.operation in ['compare', 'test']:
                    print "self.compare_performed: %s" % self.compare_performed
                    if self.compare_performed:
                        ret = self.print_compare_summary()
                        if ret:
                            print 'Print compare summary failed.'
                            print ret
    #                        return ret
                    if self.operation == 'test':
                        self.print_test_summary() # Print test results.
                elif self.operation in ['dump']:
                    # Print fail messages if any.
                    if any([chanspec for chanspec in self.chanspecs if self.operation_info[self.operation][chanspec]['status'].lower() == 'fail']):
                        print 'Fail info:'
                        for chanspec in self.chanspecs:
                            print "%s" % self.operation_info[self.operation][chanspec]['comment']

                print "Start time: {}".format(self.start_time)
                print "Total time: {}".format(str(datetime.datetime.now() - self.start_time))
                print 'end'
                    
                print 'Results directory: {}'.format(self.results_dir)
                    
                if a_test_failed:
                    return 1
                else:
                    return 0
                    
    def trafficMIMO(self, mode, duration, PM, core = None):
        ''' Taken sfrom sr,py '''
        
        self.dut = self.DUT
        self.ref = self.REF
        self.ref0 = self.REF
        dut = self.DUT
        ref = self.REF
        

#        if core==0 or core==None:
#            PM = self.PM0
#            ref = self.ref0
#        else:
#            PM = self.PM1
#            ref = self.ref1
        result = None
        self.log.info("[ %s Throughput in PM %s]" %(mode,PM))

        if dut.type == 'ap':
            dut_controller  = dut.iperf_sta
            dut_ip          = dut.iperf_intf.ip
        else:
            dut_controller  = dut
            dut_ip          = dut.INTF[0].ip
            
        print where_am_i()
        print dir(ref)
        print dir(ref.iperf_intf)
        if ref.type == 'ap':
            print where_am_i()
            ref_controller  = self.controller
            print where_am_i()
            ref_ip          = ref.iperf_intf.ip
            print where_am_i()
        else:
            ref_controller  = ref
            ref_ip          = ref.INTF[0].ip
        
        port = self.spclLib.getSockPort()
        #iperf_obj = iperf2.runIperf_c(dut=dut_controller, dutIntf=dut_ip, ref=ref_controller, refIntf=ref_ip, mode=mode, duration=self.param_iperf_duration, window_size=self.param_iperf_window_size, buffer_length=self.param_iperf_buffer_length,port=port)
        
        iperf_obj = iperf2.runIperf_c(dut=self.dut, dutIntf=self.dut.INTF[0].ip,
                                  ref=self.ref0, refIntf=self.ref0.INTF[0].ip,
                                  duration=duration, window_size='300k', buffer_length='2K',port=port)
    
        print where_am_i()
        appendStr='core1' if core else 'core0'
        
        res = iperf_obj.runThroughput(timeout=30)
        print where_am_i()
        if res!=0:
            self.log.info("Iperf Run Failed.")
            self.summary['WLAN_Traffic_'+str(appendStr)+'']='0'
            self.test_status='FAIL'
            result = -1
            return result
        else:
            result = 0
   
        #Create the plot with available results
        if str(mode).lower() == 'rx':
            
            self.dstore_addDataTable('DutRxTime_'+str(appendStr)+',DutRx_'+str(appendStr)+',RefTx_'+str(appendStr)+',DutRssi_'+str(appendStr)+',RefRate_'+str(appendStr)+'', datatable=iperf_obj.Statistics)
            
            self.tput_rx_server = float(iperf_obj.getAvgServerThroughput())
            self.tput_rx_client = float(iperf_obj.getAvgClientThroughput())
            self.log.info('Avg DUT Rx in '+str(appendStr)+':%s'%self.tput_rx_server)
            self.log.info('Avg REF Tx in '+str(appendStr)+':%s'%self.tput_rx_client)
            #self.tput_rx = float(iperf_obj.serverObj.stats['averageSpeed'])
            self.dstore_addTestSpecification('AVG_DUT_Rx_'+str(appendStr)+'', str(self.tput_rx_server))
            self.dstore_addTestSpecification('AVG_REF_Tx_'+str(appendStr)+'', str(self.tput_rx_client))
#                 self.plotdata_tput_rx.append([self.iteration_count,self.tput_rx_server])
#                 self.plot_tput_rx.createplot()
        elif str(mode).lower() == 'tx':
            
            self.dstore_addDataTable('DutTxTime_'+str(appendStr)+',RefRx_'+str(appendStr)+',DuTTx_'+str(appendStr)+',RefRssi_'+str(appendStr)+',DutRate_'+str(appendStr)+'', datatable=iperf_obj.Statistics)
            
            self.tput_tx_server = float(iperf_obj.getAvgServerThroughput())
            self.tput_tx_client = float(iperf_obj.getAvgClientThroughput())
            self.log.info('Avg DUT Tx in '+str(appendStr)+':%s'%self.tput_tx_client)
            self.log.info('Avg REF Rx in '+str(appendStr)+':%s'%self.tput_tx_server)
            self.dstore_addTestSpecification('AVG_DUT_Tx_'+str(appendStr)+'', str(self.tput_tx_client))
            self.dstore_addTestSpecification('AVG_REF_Rx_'+str(appendStr)+'', str(self.tput_tx_server))
            #self.tput_tx = float(iperf_obj.serverObj.stats['averageSpeed'])
#                 self.plotdata_tput_tx.append([self.iteration_count,self.tput_tx_server])
#                 self.plot_tput_tx.createplot()
            
        if result is None:
            self.log.error("%s_Throughput Result: Failed"%mode)
            self.summary['WLAN_Traffic_'+str(appendStr)+'']='0'
            self.test_status='FAIL'
        elif result == 0:
            self.log.info("%s_Throughput Result: Passed."%mode)
            self.summary['WLAN_Traffic_'+str(appendStr)+'']='1'
            self.test_status='PASS'
        else:
#                 self.spclLib.debug_on_fail(ref = self.ref, dut = self.dut, state = 5, device_mode = self.param_device_mode, ref1 = self.ref1, refintf = self.ref_interface, ref1intf = self.ref1_interface, controller = self.controller)
            self.log.info("%s_Throughput Result: Failed."%mode)
            self.summary['WLAN_Traffic_'+str(appendStr)+'']='0'
            self.test_status='FAIL'
        self.log.info("[!%s Throughput ]"%mode)
        return result
    
#     def trafficRSDB(self,intf):
    
    def wl_pwrstats(self, testname):
        ret, output = self.DUT.issuecmd(self.wl_prefix + 'pwrstats')    
        
        if ret:
            print ret
            return ret
        else:
            print output
            return False
            
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
