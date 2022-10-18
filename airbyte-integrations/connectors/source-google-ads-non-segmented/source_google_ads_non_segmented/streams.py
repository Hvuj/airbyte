#
# Copyright (c) 2022 Airbyte, Inc., all rights reserved.
#

from abc import ABC
from typing import Any, Iterable, List, Mapping, MutableMapping, Optional, Tuple

import pendulum
from airbyte_cdk.models import SyncMode
from airbyte_cdk.sources.streams import IncrementalMixin, Stream
from google.ads.googleads.errors import GoogleAdsException
from google.ads.googleads.v11.errors.types.authorization_error import AuthorizationErrorEnum
from google.ads.googleads.v11.errors.types.request_error import RequestErrorEnum
from google.ads.googleads.v11.services.services.google_ads_service.pagers import SearchPager

from .google_ads_constants import GoogleAds
from .models import Customer


class GoogleAdsStream(Stream, ABC):
    CATCH_API_ERRORS = True

    def __init__(self, api: GoogleAds, customers: List[Customer]):
        self.google_ads_client = api
        self.customers = customers

    def get_query(self, stream_slice: Mapping[str, Any]) -> str:
        query = GoogleAds.convert_schema_into_query(schema=self.get_json_schema(), report_name=self.name)
        print(query)
        return query

    def parse_response(self, response: SearchPager) -> Iterable[Mapping]:
        for result in response:
            yield self.google_ads_client.parse_single_result(self.get_json_schema(), result)

    def stream_slices(self, stream_state: Mapping[str, Any] = None, **kwargs) -> Iterable[Optional[Mapping[str, any]]]:
        for customer in self.customers:
            yield {"customer_id": customer.id}

    def read_records(self, stream_slice: Optional[Mapping[str, Any]] = None, **kwargs) -> Iterable[Mapping[str, Any]]:
        if stream_slice is None:
            return []

        customer_id = stream_slice["customer_id"]
        response_records = self.google_ads_client.send_request(self.get_query(stream_slice), customer_id=customer_id)
        
        try:
            for response in response_records:
                yield from self.parse_response(response)
        except GoogleAdsException as exc:
            if not self.CATCH_API_ERRORS:
                raise
            for error in exc.failure.errors:
                if error.error_code.authorization_error == AuthorizationErrorEnum.AuthorizationError.CUSTOMER_NOT_ENABLED:
                    self.logger.error(error.message)
                    continue
                # log and ignore only CUSTOMER_NOT_ENABLED error, otherwise - raise further
                raise


class IncrementalGoogleAdsStream(GoogleAdsStream, IncrementalMixin, ABC):
    days_of_data_storage = None
    primary_key = None
    # Date range is set to 15 days, because for conversion_window_days default value is 14.
    # Range less than 15 days will break the integration tests.
    range_days = 15

    def __init__(self, **kwargs):
        self._state = {}
        super().__init__(**kwargs)

    @property
    def state(self) -> MutableMapping[str, Any]:
        return self._state

    @state.setter
    def state(self, value: MutableMapping[str, Any]):
        self._state.update(value)

    def current_state(self, customer_id, default=None):
        default = default 
        return self.state.get(customer_id, {}) or default
   
            
    def get_query(self, stream_slice: Mapping[str, Any] = None) -> str:
        query = GoogleAds.convert_schema_into_query(
            schema=self.get_json_schema(),
            report_name=self.name
        )
        return query


class GeoConstants(IncrementalGoogleAdsStream):
    """
    Accounts stream: https://developers.google.com/google-ads/api/fields/v11/customer
    """


class ServiceAccounts(GoogleAdsStream):
    """
    This stream is intended to be used as a service class, not exposed to a user
    """

    CATCH_API_ERRORS = False
    primary_key = ["customer.id"]