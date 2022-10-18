import logging
import traceback
from typing import Any, Iterable, List, Mapping, MutableMapping, Tuple

from airbyte_cdk.models import SyncMode
from airbyte_cdk.sources import AbstractSource
from airbyte_cdk.sources.streams import Stream
from google.ads.googleads.errors import GoogleAdsException
from pendulum import parse, today

from .custom_query_stream import CustomQuery
from .google_ads_constants import GoogleAds
from .models import Customer
from .streams import (
    GeoConstants,
    ServiceAccounts

)


class SourceGoogleAdsNonSegmented(AbstractSource):
    @staticmethod
    def get_credentials(config: Mapping[str, Any]) -> MutableMapping[str, Any]:
        credentials = config["credentials"]
        # use_proto_plus is set to True, because setting to False returned wrong value types, which breakes the backward compatibility.
        # For more info read the related PR's description: https://github.com/airbytehq/airbyte/pull/9996
        credentials.update(use_proto_plus=True)

        # https://developers.google.com/google-ads/api/docs/concepts/call-structure#cid
        if "login_customer_id" in config and config["login_customer_id"].strip():
            credentials["login_customer_id"] = config["login_customer_id"]
        return credentials

    @staticmethod
    def get_incremental_stream_config(google_api: GoogleAds, config: Mapping[str, Any], customers: List[Customer]):
        incremental_stream_config = dict(
            api=google_api,
            customers=customers
        )
        print(incremental_stream_config)
        return incremental_stream_config

    def get_account_info(self, google_api: GoogleAds, config: Mapping[str, Any]) -> Iterable[Iterable[Mapping[str, Any]]]:
        dummy_customers = [Customer(id=_id) for _id in config["customer_id"].split(",")]
        accounts_stream = ServiceAccounts(google_api, customers=dummy_customers)
        for slice_ in accounts_stream.stream_slices():
            yield accounts_stream.read_records(sync_mode=SyncMode.full_refresh, stream_slice=slice_)

    def check_connection(self, logger: logging.Logger, config: Mapping[str, Any]) -> Tuple[bool, any]:
        try:
            logger.info("Checking the config")
            google_api = GoogleAds(credentials=self.get_credentials(config))

            accounts = self.get_account_info(google_api, config)
            customers = Customer.from_accounts(accounts)
            # Check custom query request validity by sending metric request with non-existant time window
            for customer in customers:
                for query in config.get("custom_queries", []):
                    query = query.get("query")
                    req_q = CustomQuery.insert_segments_date_expr(query)
                    response = google_api.send_request(req_q, customer_id=customer.id)
                    # iterate over the response otherwise exceptions will not be raised!
                    for _ in response:
                        pass
            return True, None
        except GoogleAdsException as exception:
            error_messages = ", ".join([error.message for error in exception.failure.errors])
            logger.error(traceback.format_exc())
            return False, f"Unable to connect to Google Ads API with the provided configuration - {error_messages}"

    def streams(self, config: Mapping[str, Any]) -> List[Stream]:
        google_api = GoogleAds(credentials=self.get_credentials(config)) 
        accounts = self.get_account_info(google_api, config)
        customers = Customer.from_accounts(accounts)
        non_manager_accounts = [customer for customer in customers if not customer.is_manager_account]
        incremental_config = self.get_incremental_stream_config(google_api, config, customers)
        non_manager_incremental_config = self.get_incremental_stream_config(google_api, config, non_manager_accounts)
        streams = [
            GeoConstants(**incremental_config)
        ]
        # Metrics streams cannot be requested for a manager account.
        if non_manager_accounts:
            streams.extend(
                [
                ]
            )
        for single_query_config in config.get("custom_queries", []):
            query = single_query_config.get("query")
            streams.append(CustomQuery(custom_query_config=single_query_config, **incremental_config))
        return streams
