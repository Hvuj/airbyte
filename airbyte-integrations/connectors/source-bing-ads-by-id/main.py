#
# Copyright (c) 2022 Airbyte, Inc., all rights reserved.
#


import sys

from airbyte_cdk.entrypoint import launch
from source_bing_ads_by_id import SourceBingAdsById

if __name__ == "__main__":
    source = SourceBingAdsById()
    launch(source, sys.argv[1:])
