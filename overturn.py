#!/usr/bin/env python
"""Execo engine to explore parameter space.

Here, the effect of Ra, Rcmb (and Pphase) on the
overturn following the crystallization of the magma ocean.
Jobs sent to Rangiroa
"""
import os
import f90nml
from threading import Thread
from execo import SshProcess, Put, sleep
from execo.log import style
from execo_engine import Engine, ParamSweeper, sweep, logger, slugify
import math


#Define general parameters
# server on which jobs are ran. Needs ssh access.
jobserver = 'rangiroa'
# Remote directory in which all jobs are sent
parent_dir = '/home/stephane/Overturn/Ched/'

class overturn(Engine):

    def create_sweeper(self):
        """Define the parameter space and return a sweeper."""
        parameters = {
            'RA': ['1.e5', '1.e6', '1.e7'],
            'RCMB' : [1.19, 3.29],
            'KFe' : [0.85, 0.9, 0.95, 0.99]
            }
        sweeps = sweep(parameters)
        self.sweeper = ParamSweeper(os.path.join(self.result_dir, "sweeps"),
                                    sweeps)

    def create_par_file(self, comb):
        """Create Run directory on remote server and upload par file"""
        logger.info('Creating and uploading par file')
        comb_dir = parent_dir + slugify(comb) + '/'
        logger.info('comb_dir = ' + comb_dir)
        # Create remote directories
        make_dirs = SshProcess('mkdir -p ' + comb_dir + 'Img ; mkdir -p ' +
                               comb_dir + 'Op ; ', jobserver).run()
        # Generate par file
        par_file = comb_dir + 'par_' + slugify(comb)
        logger.info('par_file = %s', style.emph(par_file))
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
        Put([jobserver], [par_file], remote_location=comb_dir).run()
        SshProcess('cd ' + comb_dir + ' ; mv ' + par_file+ ' par', jobserver).run()
        logger.info('Done')

    def submit_job(self, comb):
        """Use the batch script on psmn"""
        logger.info('Submit job on '+ jobserver)
        comb_dir = parent_dir + slugify(comb) + '/'
        job_sub = SshProcess('cd ' + comb_dir +
                             ' ; /usr/local/bin/qsub /home/stephane/ExamplePBS/batch_single',
                             jobserver).run()

        return job_sub.stdout.splitlines()[-1].split('.')[0]

    def is_job_running(self, job_id=None):
        """ """
        get_state = SshProcess('qstat -f ' + str(job_id), jobserver)
        get_state.ignore_exit_code = True
        get_state.run()
        return get_state.ok

    def retrieve(self):
        """ """
        SshProcess('')

    def workflow(self, comb):
        self.create_par_file(comb)
        job_id = self.submit_job(comb)
        logger.info('Combination %s will be treated by job %s',
                    slugify(comb), str(job_id))

        while self.is_job_running(job_id):
            sleep(10)

        self.sweeper.done(comb)


    def run(self):

        self.create_sweeper()
        logger.info('%s parameters combinations to be treated', len(self.sweeper.get_sweeps()))
        threads = []
        while len(self.sweeper.get_remaining()) > 0:
            comb = self.sweeper.get_next()
            logger.info('comb = %s', comb)
            t = Thread(target=self.workflow, args=(comb,))
            t.daemon = True
            threads.append(t)
            t.start()
        
        for t in threads:
			t.join()
            


if __name__ == "__main__":
    engine = overturn()
    engine.start()
