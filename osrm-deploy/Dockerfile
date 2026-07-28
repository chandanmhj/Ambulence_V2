# Standalone OSRM image for deployment (Railway, or anywhere else that just
# builds a Dockerfile without docker-compose).
#
# Unlike local dev (where osrm-extract/partition/customize are run manually
# once against a mounted volume), this bakes the ENTIRE preprocessing step
# into the image build itself, so the deployed container just needs to start
# osrm-routed - no manual setup step, no persistent volume required.
#
# HOW TO USE:
#   1. Put your bangalore.osm.pbf file in this same directory (osrm-deploy/)
#      - use a Bangalore-only extract (via `osmium extract` with a bounding
#        box), NOT the full southern-zone file, or the image build will be
#        very large and slow. See DEPLOYMENT.md for the exact command.
#   2. On Railway: create a new service, point it at this directory
#      (osrm-deploy/) as the root, and it will build this Dockerfile
#      automatically.

FROM osrm/osrm-backend AS builder

WORKDIR /data
COPY bangalore.osm.pbf /data/bangalore.osm.pbf

RUN osrm-extract -p /opt/car.lua /data/bangalore.osm.pbf \
 && osrm-partition /data/bangalore.osrm \
 && osrm-customize /data/bangalore.osrm

FROM osrm/osrm-backend

WORKDIR /data
COPY --from=builder /data /data

EXPOSE 5000

CMD ["osrm-routed", "--algorithm", "mld", "/data/bangalore.osrm"]
