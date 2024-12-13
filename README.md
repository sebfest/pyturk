# pyturk

## Project Description

pyturk is a primitive client that I wrote at work to facilitate working with Qualtrics.

## Getting Started

1. You can install pyturk locally in your working environment using pip:

   > pip install 'git+ssh://git@github.com/sebfest/pyturk.git'

   Or by first cloning this repository and then running pip 

   > git clone git@github.com:sebfest/pyturk.git
   > 
   > cd pyturk
   > 
   > pip install .


3. Load the client:
   ```pycon
   from pyturk.managers import HitManager, QualificationManager
   
   hitmanager = HitManager(sandbox=False)
   hit = hitmanager.download_hit()
   
   qualification_manager = QualificationManager(sandbox=False)
   qualification = qualification_manager.get_qualification()
    
   hit.add_qualification_to_hit(qualification)
   hit.assign_qualification_to_workers()
   ```
## Contributing Members

**Team Leads (Contacts) : [Sebastian Fest](https://github.com/sebfest)**