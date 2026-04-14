content = open('app_v13.py', encoding='utf-8').read()

publisher_code = '''
# ── Google Ads Library ───────────────────────────────────────
try:
    from google.ads.googleads.client import GoogleAdsClient
    from google.ads.googleads.errors import GoogleAdsException
    GOOGLE_ADS_AVAILABLE = True
except ImportError:
    GOOGLE_ADS_AVAILABLE = False
    print("⚠️ google-ads library not installed")

GOOGLE_ADS_CONFIG = {
    "developer_token":   GOOGLE_ADS_DEV_TOK,
    "client_id":         GOOGLE_CLIENT_ID,
    "client_secret":     GOOGLE_CLIENT_SEC,
    "refresh_token":     GOOGLE_REFRESH_TOK,
    "login_customer_id": GOOGLE_MCC_ID.replace("-",""),
    "use_proto_plus":    True
}

class GoogleAdsPublisher:
    def __init__(self, customer_id: str):
        self.customer_id = customer_id.replace("-","").replace(" ","")
        self.client = GoogleAdsClient.load_from_dict(GOOGLE_ADS_CONFIG)

    def publish(self, result: dict, request: dict) -> dict:
        results = {
            "success": False,
            "budget_resource": "",
            "search_campaign": "",
            "pmax_campaign": "",
            "keywords_added": 0,
            "ad_groups_created": 0,
            "ads_created": 0,
            "sitelinks_created": 0,
            "extensions_created": 0,
            "errors": [],
            "status": "PAUSED",
            "published_agents": []
        }
        try:
            daily_budget = float(request.get("daily_budget", 50))
            business_name = request.get("business_name", "Business")
            website_url = request.get("website_url", "https://example.com")
            conversion_goal = request.get("conversion_goal", "Leads")

            # ── 1. Create Shared Budget (from A18 Budget Allocator) ──
            budget_plan = result.get("budget_plan", {})
            actual_budget = float(budget_plan.get("daily_budget", daily_budget))
            bsvc = self.client.get_service("CampaignBudgetService")
            bop = self.client.get_type("CampaignBudgetOperation")
            b = bop.create
            b.name = f"AdsForge Budget {int(time.time())}"
            b.amount_micros = int(actual_budget * 1_000_000)
            b.delivery_method = self.client.enums.BudgetDeliveryMethodEnum.STANDARD
            b.explicitly_shared = True
            br = bsvc.mutate_campaign_budgets(
                customer_id=self.customer_id, operations=[bop]
            )
            budget_res = br.results[0].resource_name
            results["budget_resource"] = budget_res
            results["published_agents"].append("A18: Budget Allocator")
            log.info(f"✅ Budget created: {budget_res}")

            # ── 2. Create Search Campaign (from A17 Campaign Architect) ──
            csvc = self.client.get_service("CampaignService")
            cop = self.client.get_type("CampaignOperation")
            c = cop.create
            c.name = f"[AdsForge] {business_name} — Search"
            c.status = self.client.enums.CampaignStatusEnum.PAUSED
            c.advertising_channel_type = self.client.enums.AdvertisingChannelTypeEnum.SEARCH
            c.campaign_budget = budget_res
            c.maximize_conversions.target_cpa_micros = 0
            c.network_settings.target_google_search = True
            c.network_settings.target_search_network = True
            c.network_settings.target_content_network = False
            cr = csvc.mutate_campaigns(
                customer_id=self.customer_id, operations=[cop]
            )
            camp_res = cr.results[0].resource_name
            results["search_campaign"] = camp_res
            results["published_agents"].append("A17: Campaign Architect")
            log.info(f"✅ Search campaign created: {camp_res}")

            # ── 3. Location Targeting (from A21 Geo Targeting) ──
            targeting = result.get("targeting", {})
            location = request.get("target_location", "")
            if location:
                try:
                    gsvc = self.client.get_service("GoogleAdsService")
                    ccsvc = self.client.get_service("CampaignCriterionService")
                    loc_parts = location.split(",")
                    loc_name = loc_parts[0].strip()
                    query = f"""
                        SELECT geo_target_constant.resource_name
                        FROM geo_target_constant
                        WHERE geo_target_constant.canonical_name LIKE '%{loc_name}%'
                        LIMIT 1
                    """
                    geo_resp = gsvc.search(customer_id=self.customer_id, query=query)
                    for row in geo_resp:
                        crit_op = self.client.get_type("CampaignCriterionOperation")
                        crit_op.create.campaign = camp_res
                        crit_op.create.location.geo_target_constant = row.geo_target_constant.resource_name
                        ccsvc.mutate_campaign_criteria(
                            customer_id=self.customer_id, operations=[crit_op]
                        )
                        results["published_agents"].append("A21: Geo Targeting")
                        log.info(f"✅ Location targeted: {loc_name}")
                        break
                except Exception as e:
                    results["errors"].append(f"Location targeting: {e}")

            # ── 4. Negative Keywords (from A06 Negative Mining) ──
            neg_data = result.get("negative_keywords", {})
            neg_kws = neg_data.get("campaign_level_negatives", [])
            if neg_kws:
                try:
                    ccsvc2 = self.client.get_service("CampaignCriterionService")
                    neg_ops = []
                    for kw in neg_kws[:50]:
                        op = self.client.get_type("CampaignCriterionOperation")
                        cr2 = op.create
                        cr2.campaign = camp_res
                        cr2.negative = True
                        cr2.keyword.text = str(kw)[:80]
                        cr2.keyword.match_type = self.client.enums.KeywordMatchTypeEnum.BROAD
                        neg_ops.append(op)
                    if neg_ops:
                        ccsvc2.mutate_campaign_criteria(
                            customer_id=self.customer_id, operations=neg_ops
                        )
                        results["published_agents"].append("A06: Negative Mining")
                        log.info(f"✅ {len(neg_ops)} negative keywords added")
                except Exception as e:
                    results["errors"].append(f"Negatives: {e}")

            # ── 5. STAG Ad Groups + Keywords (from A04 STAG Keywords) ──
            kw_data = result.get("keywords", {})
            services = kw_data.get("keywords_by_service", {})
            ad_copy = result.get("ad_copy", {})
            headlines = ad_copy.get("headlines", [])
            descs = ad_copy.get("descriptions", [])

            FORBIDDEN = ["near me","nearby","cheap","cheapest","free","jobs",
                        "career","how to","diy","wikipedia","best","top",
                        "discount","hiring","salary"]

            agsvc = self.client.get_service("AdGroupService")
            agcsvc = self.client.get_service("AdGroupCriterionService")
            adasvc = self.client.get_service("AdGroupAdService")

            if services:
                for svc_name, kws in list(services.items())[:10]:
                    try:
                        # Create Ad Group per service (STAG)
                        agop = self.client.get_type("AdGroupOperation")
                        ag = agop.create
                        ag.name = f"{business_name} — {svc_name}"[:255]
                        ag.campaign = camp_res
                        ag.status = self.client.enums.AdGroupStatusEnum.ENABLED
                        ag.type_ = self.client.enums.AdGroupTypeEnum.SEARCH_STANDARD
                        ag.cpc_bid_micros = 2_000_000
                        agr = agsvc.mutate_ad_groups(
                            customer_id=self.customer_id, operations=[agop]
                        )
                        ag_res = agr.results[0].resource_name
                        results["ad_groups_created"] += 1

                        # Add keywords for this service
                        clean_kws = []
                        for k in kws:
                            text = k["keyword"] if isinstance(k, dict) else str(k)
                            if not any(f in text.lower() for f in FORBIDDEN):
                                clean_kws.append(text)

                        if clean_kws:
                            kwops = []
                            for kw in clean_kws[:20]:
                                op = self.client.get_type("AdGroupCriterionOperation")
                                cr3 = op.create
                                cr3.ad_group = ag_res
                                cr3.status = self.client.enums.AdGroupCriterionStatusEnum.ENABLED
                                cr3.keyword.text = kw[:80]
                                cr3.keyword.match_type = self.client.enums.KeywordMatchTypeEnum.PHRASE
                                kwops.append(op)
                            agcsvc.mutate_ad_group_criteria(
                                customer_id=self.customer_id, operations=kwops
                            )
                            results["keywords_added"] += len(kwops)

                        # Create RSA Ad for this ad group (from A08)
                        if len(headlines) >= 3 and len(descs) >= 2:
                            adaop = self.client.get_type("AdGroupAdOperation")
                            aa = adaop.create
                            aa.ad_group = ag_res
                            aa.status = self.client.enums.AdGroupAdStatusEnum.ENABLED
                            rsa = aa.ad.responsive_search_ad
                            for hl in headlines[:15]:
                                asset = self.client.get_type("AdTextAsset")
                                asset.text = hl[:30]
                                rsa.headlines.append(asset)
                            for desc in descs[:4]:
                                asset = self.client.get_type("AdTextAsset")
                                asset.text = desc[:90]
                                rsa.descriptions.append(asset)
                            aa.ad.final_urls.append(website_url)
                            adasvc.mutate_ad_group_ads(
                                customer_id=self.customer_id, operations=[adaop]
                            )
                            results["ads_created"] += 1

                    except Exception as e:
                        results["errors"].append(f"Ad group {svc_name}: {e}")

                results["published_agents"].append("A04: STAG Keywords")
                results["published_agents"].append("A08: RSA Copywriter")

            # ── 6. Sitelink Extensions (from A26 Extension Suite) ──
            extensions = result.get("extensions", {})
            sitelinks = extensions.get("sitelinks", []) or ad_copy.get("sitelinks", [])
            if sitelinks:
                try:
                    asset_svc = self.client.get_service("AssetService")
                    camp_asset_svc = self.client.get_service("CampaignAssetService")
                    for sl in sitelinks[:6]:
                        title = (sl.get("title") or sl.get("link_text") or "")[:25]
                        desc1 = (sl.get("description1") or sl.get("description") or "")[:35]
                        desc2 = (sl.get("description2") or "")[:35]
                        sl_url = sl.get("url", website_url)
                        if not title:
                            continue
                        asset_op = self.client.get_type("AssetOperation")
                        asset = asset_op.create
                        asset.sitelink_asset.link_text = title
                        asset.sitelink_asset.description1 = desc1
                        asset.sitelink_asset.description2 = desc2
                        asset.final_urls.append(sl_url)
                        asset_resp = asset_svc.mutate_assets(
                            customer_id=self.customer_id, operations=[asset_op]
                        )
                        asset_rn = asset_resp.results[0].resource_name
                        camp_asset_op = self.client.get_type("CampaignAssetOperation")
                        camp_asset = camp_asset_op.create
                        camp_asset.campaign = camp_res
                        camp_asset.asset = asset_rn
                        camp_asset.field_type = self.client.enums.AssetFieldTypeEnum.SITELINK
                        camp_asset_svc.mutate_campaign_assets(
                            customer_id=self.customer_id, operations=[camp_asset_op]
                        )
                        results["sitelinks_created"] += 1
                    results["published_agents"].append("A26: Extension Suite")
                    log.info(f"✅ {results['sitelinks_created']} sitelinks created")
                except Exception as e:
                    results["errors"].append(f"Sitelinks: {e}")

            # ── 7. Callout Extensions (from A26) ──
            callouts = extensions.get("callouts", [])
            if callouts:
                try:
                    asset_svc2 = self.client.get_service("AssetService")
                    camp_asset_svc2 = self.client.get_service("CampaignAssetService")
                    for callout_text in callouts[:10]:
                        text = str(callout_text)[:25]
                        asset_op = self.client.get_type("AssetOperation")
                        asset_op.create.callout_asset.callout_text = text
                        asset_resp = asset_svc2.mutate_assets(
                            customer_id=self.customer_id, operations=[asset_op]
                        )
                        asset_rn = asset_resp.results[0].resource_name
                        camp_asset_op = self.client.get_type("CampaignAssetOperation")
                        camp_asset = camp_asset_op.create
                        camp_asset.campaign = camp_res
                        camp_asset.asset = asset_rn
                        camp_asset.field_type = self.client.enums.AssetFieldTypeEnum.CALLOUT
                        camp_asset_svc2.mutate_campaign_assets(
                            customer_id=self.customer_id, operations=[camp_asset_op]
                        )
                        results["extensions_created"] += 1
                except Exception as e:
                    results["errors"].append(f"Callouts: {e}")

            # ── 8. Conversion Actions (from A22 Conv Tracking) ──
            conv_data = result.get("conversion_tracking", {})
            conv_actions = conv_data.get("conversion_actions", [])
            if conv_actions:
                try:
                    conv_svc = self.client.get_service("ConversionActionService")
                    for action in conv_actions[:3]:
                        conv_op = self.client.get_type("ConversionActionOperation")
                        ca = conv_op.create
                        ca.name = action.get("name", "Lead")[:100]
                        ca.status = self.client.enums.ConversionActionStatusEnum.ENABLED
                        ca.type_ = self.client.enums.ConversionActionTypeEnum.WEBPAGE
                        ca.category = self.client.enums.ConversionActionCategoryEnum.LEAD
                        ca.value_settings.default_value = float(action.get("value", 1.0))
                        ca.value_settings.always_use_default_value = True
                        conv_svc.mutate_conversion_actions(
                            customer_id=self.customer_id, operations=[conv_op]
                        )
                    results["published_agents"].append("A22: Conv Tracking")
                except Exception as e:
                    results["errors"].append(f"Conversions: {e}")

            results["success"] = True
            log.info(f"✅ Published {len(results['published_agents'])} agent results to Google Ads")
            return results

        except Exception as e:
            results["errors"].append(str(e))
            log.error(f"❌ Publish failed: {e}")
            return results
'''

if 'class GoogleAdsPublisher' not in content:
    content = content.replace(
        'if __name__ == "__main__":',
        publisher_code + '\nif __name__ == "__main__":'
    )
    open('app_v13.py', 'w', encoding='utf-8').write(content)
    print('Done! Full GoogleAdsPublisher added with all agents.')
else:
    print('Already exists - removing old and adding new')
    # Remove old class
    start = content.find('class GoogleAdsPublisher')
    if start > 0:
        # Find end of class
        next_class = content.find('\nclass ', start + 1)
        next_def = content.find('\n@app.', start + 1)
        if next_class == -1:
            next_class = 999999
        if next_def == -1:
            next_def = 999999
        end = min(next_class, next_def)
        content = content[:start] + content[end:]
        content = content.replace(
            'if __name__ == "__main__":',
            publisher_code + '\nif __name__ == "__main__":'
        )
        open('app_v13.py', 'w', encoding='utf-8').write(content)
        print('Done! Replaced old GoogleAdsPublisher with full version.')