#!/usr/bin/env python
'''
Created on May 13, 2015

@author: leblancr

Copyright here All Rights Reserved
Broadcom confidential
'''

import sys
import subprocess

class CheckReg(object):
    """ Class to read chip info and check values against table. """

    def __init__(self):
        self.chip_num = ''
        self.phy_rev = ''
        self.ref_phyreg = {}
        self.ref_phytable = {}
        self.ref_radioreg = {}
        self.ref_files = {'4350': {'phyreg': '4350_phyreg.txt',
                                   'phytable': '4350_phytable.txt',
                                   'radioreg': '4350_radioreg.txt',
                                   }
                          }
        
    def get_chip_info(self):
        ''' '''
        cmd = ['wl', 'revinfo']
        print "Issue wl rev info"
        try:
    #        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True)
            proc = subprocess.Popen(cmd, stdout = subprocess.PIPE, stderr = subprocess.PIPE)
            output, ret = proc.communicate()
            print "return code: %s" % ret
            print "output: \n%s" % output
            proc.wait()
    
            if ret:
                print "Error: %s" % ret
                sys.exit() 
            else:
                for line in output.splitlines():
#                    print line
                    if 'chipnum' in line:
                        self.chip_num = line.split()[1][2:]
                    elif 'phyrev' in line:
                        self.phy_rev = line.split()[1][2:]
    
        except subprocess.CalledProcessError as e:
            print "Error: %s" % e
#            return (1)
                
        print "chip_num: %s" % self.chip_num
        print "phy_rev: %s" % self.phy_rev
        
    def get_reference_tables(self):
        ''' '''
        
        ref_file = self.ref_files[self.chip_num]['phyreg']
        print "Reading %s" % ref_file
        with open("%s" % ref_file) as f:
            for line in f:
                key, value = line.strip().split()
#                print key, value
                if key[:2] != '0x':
                    key = '0x' + key
                if value[:2] != '0x':
                    value = '0x' + value
                
                self.ref_phyreg[key] = value
                
#        for k, v in self.ref_phyreg.iteritems():
#            print k, v
        
        ref_file = self.ref_files[self.chip_num]['phytable']
        print "Reading %s" % ref_file
        with open("%s" % ref_file) as f:
            for line in f:
                items = line.strip().split()
                key = items[0][:-1]
                values = items[1:]
                if key[:2] != '0x':
                    key = '0x' + key
#                print key, values
                self.ref_phytable[key] = values
                
#        for k, v in self.ref_phytable.iteritems():
#            print k, v
        
        ref_file = self.ref_files[self.chip_num]['radioreg']
        print "Reading %s" % ref_file
        with open("%s" % ref_file) as f:
            for line in f:
                items = line.strip().split()
                key = items[0]
                if key[:2] != '0x':
                    key = '0x' + key
                values = [x if x[:2] == '0x' else '0x' + x for x in items[1:]]
                self.ref_radioreg[key] = values
                    
#        for k, v in self.ref_radioreg.iteritems():
#            print k, v

        
    def compare_phyreg_values(self):
        ''' '''
        
        print 'Register, chip value, reference value:'

        for reg, ref_value in self.ref_phyreg.iteritems():
            cmd = ['wl', 'phyreg', '%s' % reg]
#            print "Issue %s" % ' '.join(cmd)
            try:
                proc = subprocess.Popen(cmd, stdout = subprocess.PIPE, stderr = subprocess.PIPE)
                output, ret = proc.communicate()
#                print "return code: %s" % ret
#                print "output: \n%s" % output
                proc.wait()
        
                if ret:
                    print "Error: %s" % ret
#                    sys.exit()
                else:
                    for line in output.splitlines():
                        if line == ref_value:
                            print "%s %s %s" % (reg, line, ref_value)
                        else:
                            print "%s %s %s  <- Doesn't match" % (reg, line, ref_value)
                            
        
            except subprocess.CalledProcessError as e:
                print "Error: %s" % e
            
    def compare_phytable_values(self):
        ''' '''
        
    def compare_radioreg_values(self):
        ''' '''
        
        print 'Register, chip value, reference value:'
        
        for reg, ref_value in self.ref_radioreg.iteritems():
            cmd = ['wl', 'radioreg', '%s' % reg]
#            print "Issue %s" % ' '.join(cmd)
            try:
                proc = subprocess.Popen(cmd, stdout = subprocess.PIPE, stderr = subprocess.PIPE)
                output, ret = proc.communicate()
#                print "return code: %s" % ret
#                print "output: \n%s" % output
                proc.wait()
        
                if ret:
                    print "Error: %s" % ret
#                    sys.exit()
                else:
                    for line in output.splitlines():
                        if line == ref_value:
                            print "%s %s %s" % (reg, line, ref_value)
                        else:
                            print "%s %s %s  <- Doesn't match" % (reg, line, ref_value)
                            
        
            except subprocess.CalledProcessError as e:
                print "Error: %s" % e
            
def _main():
    ''' '''

    cr = CheckReg()
    cr.get_chip_info()
    cr.get_reference_tables()
    cr.compare_phyreg_values()
#    cr.compare_phytable_values()
#    cr.compare_radioreg_values()
    
if __name__ == "__main__":
    sys.exit(_main())

