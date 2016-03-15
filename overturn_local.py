#!/usr/bin/env python
"""Execo engine to explore parameter space.

This script is meant to run directly on the cluster
to avoid the many ssh processes to at each stage.
Here, the effect of Ra, Rcmb (and Pphase) on the
overturn following the crystallization of the magma ocean.
Jobs sent to Rangiroa
"""
import os
import f90nml
from threading import Thread
from execo import sleep
from execo_engine import Engine, ParamSweeper, sweep, logger, slugify
import math
import subprocess as sp

#Define general parameters
# server on which jobs are ran. Needs ssh access.
jobserver = 'rangiroa'
# Remote directory in which all jobs are sent
parent_dir = '/home/stephane/Overturn/Ched2/'

class overturn(Engine):

    def create_sweeper(self):
        """Define the parameter space and return a sweeper."""
        parameters = {
            'RA': ['1.e5', '1.e6'],
            'RCMB' : [1.19, 3.29],
            'KFe' : [0.85, 0.9]
            }
        sweeps = sweep(parameters)
        self.sweeper = ParamSweeper(os.path.join(self.result_dir, "sweeps"),
                                    sweeps)

    def create_par_file(self, comb):
        """Create Run directory on remote server and upload par file"""
        logger.info('Creating par file')
        comb_dir = parent_dir + slugify(comb) + '/'
        logger.info('comb_dir = ' + comb_dir)
        # Create remote directories
        
        mdir = sp.call('mkdir -p ' + comb_dir + 'Img ; mkdir -p ' + comb_dir + 'Op ; ', shell=True)
        # Generate par file
        par_file = 'par_' + slugify(comb)
        nml = f90nml.read('template.nml')
        nml['refstate']['ra0'] = float(comb['RA'])
        nml['tracersin']['K_Fe'] = comb['KFe']
        nml['geometry']['r_cmb'] = comb['RCMB']
        nztot = min(int(2**(math.log10(float(comb['RA']))+1)), 128)
        nml['geometry']['nztot'] = nztot
        nml['geometry']['nytot'] = int(math.pi*(comb['RCMB']+0.5)*nztot)
        nml.write(par_file, force=True)
        logger.info('Created par file ' + par_file)
        # Upload par file to remote directory
        cpar = sp.call('cp ' + par_file + ' ' + comb_dir, shell=True)
        mpar = sp.call('cd ' + comb_dir + ' ; mv ' + par_file+ ' par', shell=True)
        logger.info('Done')

    def submit_job(self, comb):
        """Use the batch script"""
        logger.info('Submiting job on '+ jobserver)
        comb_dir = parent_dir + slugify(comb) + '/'
        job_sub = sp.Popen('cd ' + comb_dir +
                             ' ; /usr/local/bin/qsub /home/stephane/ExamplePBS/batch_single',
                             shell=True,
                             stdout=sp.PIPE, stderr=sp.STDOUT)
        #        print 'job : ',job_sub.stdout
        # print('job=', job_sub.stdout.readlines())
        line = job_sub.stdout.readlines()[-1]
        # for line in job_sub.stdout.readlines():
        print('line=', line , line.split('.')[0])
        retval = job_sub.wait()
        return job_sub.stdout.readlines()[-1].split('.')[0]

    def workflow(self, comb):
        self.create_par_file(comb)
        job_id = self.submit_job(comb)
        logger.info('Combination %s will be treated by job %s',
                    slugify(comb), str(job_id))
        self.sweeper.done(comb)

    def run(self):
        self.create_sweeper()
        logger.info('%s parameters combinations to be treated', len(self.sweeper.get_sweeps()))
        threads = []
        while len(self.sweeper.get_remaining()) > 0:
            comb = self.sweeper.get_next()
            t = Thread(target=self.workflow, args=(comb,))
            t.daemon = True
            threads.append(t)
            t.start()


if __name__ == "__main__":
    engine = overturn()
    engine.start()
