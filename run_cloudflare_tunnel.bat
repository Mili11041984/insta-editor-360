@echo off
title Insta Editor 360 - Permanent Cloudflare Tunnel
echo ========================================================
echo  STARTING PERMANENT CLOUDFLARE TUNNEL (INSTA EDITOR 360)
echo ========================================================
"%~dp0cloudflared.exe" tunnel run --token eyJhIjoiNzExNDc4YjQxN2M0MTI4NDAxZDEzMWYyZmRhMWJlY2QiLCJ0IjoiNDY5NWE1NDgtY2I4Ny00MDdjLTliZTMtYjMyMDFkNzY0NDJkIiwicyI6Ik9UUmtZemxtWmpRdE1URmpaUzAwTkdOakxUaG1aV1l0TjJRNE9UVTNZek5tT0RRNCJ9
pause
