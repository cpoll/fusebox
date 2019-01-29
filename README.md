Remote workspace w/ AWS EC2 and an S3-FUSE storage drive. 


# Steps
- Modify stack_config.yml

- Run tropo.py

- Test dynamic inventory
    - EC2_INI_PATH=./ansible/ec2.ini ansible -m ping tag_InstanceResponsibility_Fusebox

- Run Ansible
    - export AWS_ACCESS_KEY_ID='asd'
    - export AWS_SECRET_ACCESS_KEY='asd'
    - cd ansible
    - curl https://raw.githubusercontent.com/ansible/ansible/devel/contrib/inventory/ec2.py > ec2.py
    - ansible-playbook -i ec2.py fusebox.yml 