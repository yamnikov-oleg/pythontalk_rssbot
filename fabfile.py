from fabric import task


@task
def upgrade(c):
    c.local("docker build . -t registry.gitlab.com/yamnikov-oleg/pythontalk-rssbot")
    c.local("docker push registry.gitlab.com/yamnikov-oleg/pythontalk-rssbot")

    with c.cd("pythontalk"):
        c.run("docker-compose pull rssbot")
        c.run("docker-compose up -d rssbot")
