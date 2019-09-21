Remote workspace w/ AWS EC2 and an S3-FUSE storage drive.


# Steps
- Modify stack_config.yml

- Run tropo.py

- Run Ansible
    - ssh add [FUSEBOX_SSH_KEY]
    - ANSIBLE_USER=ubuntu ansible-playbook -i inventories/fusebox.aws_ec2.py fusebox.yml

- Every other time, run ansible using the user specified in inventories/group_vars/all.yml