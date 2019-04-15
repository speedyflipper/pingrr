message=$1
echo $message
git add -A
git commit -a -m "$message"
git push -u origin master
