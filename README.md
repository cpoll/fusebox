Remote workspace w/ AWS EC2 and an S3-FUSE storage drive.


# Steps
- Modify stack_config.yml

- Run tropo.py

- Test dynamic inventory
    - EC2_INI_PATH=./ansible/ec2.ini ansible -m ping tag_InstanceResponsibility_Fusebox

- Run Ansible
    - ssh add [FUSEBOX_SSH_KEY]
    - ansible-playbook -i inventories/fusebox.aws_ec2.py -e "ansible_ssh_user=ubuntu" fusebox.yml