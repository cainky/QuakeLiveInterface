# Quake Live Dedicated Server with minqlx
# Uses Ubuntu 16.04 which has Python 3.5

FROM ubuntu:16.04

ENV DEBIAN_FRONTEND=noninteractive

# Install dependencies
RUN dpkg --add-architecture i386 && \
    apt-get update && \
    apt-get install -y \
        lib32gcc1 \
        lib32stdc++6 \
        libc6-i386 \
        wget \
        ca-certificates \
        python3 \
        python3-dev \
        python3-pip \
        git \
        && rm -rf /var/lib/apt/lists/*

# Install Python packages for minqlx
RUN pip3 install redis hiredis

# Create steam user
RUN useradd -m steam
WORKDIR /home/steam

# Install SteamCMD
RUN mkdir -p steamcmd && \
    cd steamcmd && \
    wget -q https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz && \
    tar -xzf steamcmd_linux.tar.gz && \
    rm steamcmd_linux.tar.gz

# Download Quake Live Dedicated Server
RUN cd steamcmd && \
    ./steamcmd.sh +force_install_dir /home/steam/ql +login anonymous +app_update 349090 validate +quit

# Download and install minqlx
RUN cd /home/steam/ql && \
    wget -q https://github.com/MinoMino/minqlx/releases/download/v0.5.2/minqlx_v0.5.2.tar.gz && \
    tar -xzf minqlx_v0.5.2.tar.gz && \
    rm minqlx_v0.5.2.tar.gz

# Clone minqlx-plugins
RUN cd /home/steam/ql && \
    git clone https://github.com/MinoMino/minqlx-plugins.git

# Create config directory
RUN mkdir -p /home/steam/.quakelive/27960/baseq3

# Copy our agent plugin (will be mounted or copied at runtime)
COPY minqlx-plugin/ql_agent_plugin.py /home/steam/ql/minqlx-plugins/

# Create server config
RUN echo 'set sv_hostname "AgentTraining"\n\
set sv_tags "ffa,training"\n\
set sv_maxclients 8\n\
set g_gametype 0\n\
set timelimit 0\n\
set fraglimit 0\n\
set g_inactivity 0\n\
set g_allowVote 0\n\
set qlx_owner "STEAM_ID_PLACEHOLDER"\n\
set qlx_plugins "ql_agent_plugin"\n\
set qlx_redisAddress "redis"\n\
set qlx_redisPort "6379"\n\
set qlx_redisDatabase "0"\n\
set qlx_agentSteamId "STEAM_ID_PLACEHOLDER"' > /home/steam/.quakelive/27960/baseq3/server.cfg

# Set ownership
RUN chown -R steam:steam /home/steam

USER steam
WORKDIR /home/steam/ql

# Expose ports
EXPOSE 27960/udp 27960/tcp 28960/tcp

# Inline entrypoint script - runs vanilla server with LAN mode enabled
RUN echo '#!/bin/bash\n\
STEAM_ID="${STEAM_ID:-76561197984141695}"\n\
MAP="${MAP:-campgrounds}"\n\
echo "Starting QL Server (LAN mode) - Map: $MAP"\n\
cd /home/steam/ql\n\
exec ./run_server_x64.sh \\\n\
  +set sv_hostname "AgentTraining" \\\n\
  +set g_gametype 0 \\\n\
  +set sv_lanForceRate 1 \\\n\
  +set sv_strictAuth 0 \\\n\
  +set sv_pure 0 \\\n\
  +set sv_maxclients 8 \\\n\
  +set timelimit 0 \\\n\
  +set fraglimit 0 \\\n\
  +set g_inactivity 0 \\\n\
  +map "$MAP"\n\
' > /home/steam/entrypoint.sh && chmod +x /home/steam/entrypoint.sh

ENTRYPOINT ["/bin/bash", "/home/steam/entrypoint.sh"]
