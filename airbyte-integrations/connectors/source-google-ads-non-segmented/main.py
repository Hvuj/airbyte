#
# Copyright (c) 2022 Airbyte, Inc., all rights reserved.
#


import sys

from airbyte_cdk.entrypoint import launch
from source_google_ads_non_segmented import SourceGoogleAdsNonSegmented

if __name__ == "__main__":
    source = SourceGoogleAdsNonSegmented()
    launch(source, sys.argv[1:])
