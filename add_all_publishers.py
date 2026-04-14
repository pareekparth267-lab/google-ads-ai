content = open('app_v13.py', encoding='utf-8').read()

pmax_code = '''
    def publish_pmax(self, result: dict, request: dict, budget_res: str) -> dict:
        """A09 — Create Performance Max Campaign"""
        try:
            business_name = request.get("business_name", "Business")
            website_url = request.get("website_url", "https://example.com")
            pmax_data = result.get("performance_max", {})
            
            # Create PMax Campaign
            csvc = self.client.get_service("CampaignService")
            cop = self.client.get_type("CampaignOperation")
            c = cop.create
            c.name = f"[AdsForge] {business_name} — PMax"
            c.status = self.client.enums.CampaignStatusEnum.PAUSED
            c.advertising_channel_type = self.client.enums.AdvertisingChannelTypeEnum.PERFORMANCE_MAX
            c.campaign_budget = budget_res
            c.maximize_conversion_value.target_roas = 0
            cr = csvc.mutate_campaigns(
                customer_id=self.customer_id, operations=[cop]
            )
            camp_res = cr.results[0].resource_name
            log.info(f"✅ PMax campaign created: {camp_res}")

            # Create Asset Group
            ag_svc = self.client.get_service("AssetGroupService")
            asset_svc = self.client.get_service("AssetService")
            
            asset_groups = pmax_data.get("asset_groups", [])
            if not asset_groups:
                asset_groups = [{"headlines": result.get("ad_copy", {}).get("headlines", []),
                               "descriptions": result.get("ad_copy", {}).get("descriptions", [])}]
            
            for ag_data in asset_groups[:1]:
                agop = self.client.get_type("AssetGroupOperation")
                ag = agop.create
                ag.name = f"{business_name} — Asset Group 1"
                ag.campaign = camp_res
                ag.status = self.client.enums.AssetGroupStatusEnum.ENABLED
                ag.final_urls.append(website_url)
                ag_res = ag_svc.mutate_asset_groups(
                    customer_id=self.customer_id, operations=[agop]
                ).results[0].resource_name

                # Add text assets
                ag_asset_svc = self.client.get_service("AssetGroupAssetService")
                headlines = ag_data.get("headlines", [])[:5]
                descriptions = ag_data.get("descriptions", [])[:5]
                
                for hl in headlines:
                    asset_op = self.client.get_type("AssetOperation")
                    asset_op.create.text_asset.text = hl[:30]
                    asset_rn = asset_svc.mutate_assets(
                        customer_id=self.customer_id, operations=[asset_op]
                    ).results[0].resource_name
                    
                    aga_op = self.client.get_type("AssetGroupAssetOperation")
                    aga = aga_op.create
                    aga.asset_group = ag_res
                    aga.asset = asset_rn
                    aga.field_type = self.client.enums.AssetFieldTypeEnum.HEADLINE
                    ag_asset_svc.mutate_asset_group_assets(
                        customer_id=self.customer_id, operations=[aga_op]
                    )

                for desc in descriptions:
                    asset_op = self.client.get_type("AssetOperation")
                    asset_op.create.text_asset.text = desc[:90]
                    asset_rn = asset_svc.mutate_assets(
                        customer_id=self.customer_id, operations=[asset_op]
                    ).results[0].resource_name
                    
                    aga_op = self.client.get_type("AssetGroupAssetOperation")
                    aga = aga_op.create
                    aga.asset_group = ag_res
                    aga.asset = asset_rn
                    aga.field_type = self.client.enums.AssetFieldTypeEnum.DESCRIPTION
                    ag_asset_svc.mutate_asset_group_assets(
                        customer_id=self.customer_id, operations=[aga_op]
                    )

            return {"success": True, "pmax_campaign": camp_res}
        except Exception as e:
            log.error(f"PMax error: {e}")
            return {"success": False, "error": str(e)}

    def publish_audiences(self, result: dict, request: dict) -> dict:
        """A20 — Create Remarketing Lists"""
        try:
            business_name = request.get("business_name", "Business")
            audience_data = result.get("audiences", {})
            remarketing = audience_data.get("remarketing_audiences", [])
            
            ulist_svc = self.client.get_service("UserListService")
            created = []
            
            for rm in remarketing[:5]:
                op = self.client.get_type("UserListOperation")
                ul = op.create
                ul.name = f"[AdsForge] {rm.get('name', 'Visitors')}"
                ul.description = rm.get("targeting_rule", "Website visitors")
                ul.membership_status = self.client.enums.UserListMembershipStatusEnum.OPEN
                ul.membership_life_span = int(rm.get("membership_duration_days", 30))
                ul.rule_based_user_list.flexible_rule_user_list.inclusive_rule_operator = (
                    self.client.enums.UserListFlexibleRuleOperatorEnum.AND
                )
                resp = ulist_svc.mutate_user_lists(
                    customer_id=self.customer_id, operations=[op]
                )
                created.append(resp.results[0].resource_name)
                log.info(f"✅ Audience created: {rm.get('name')}")

            return {"success": True, "audiences_created": len(created)}
        except Exception as e:
            log.error(f"Audience error: {e}")
            return {"success": False, "error": str(e)}

    def publish_smart_bidding(self, result: dict, camp_res: str) -> dict:
        """A19 — Set Smart Bidding on Campaign"""
        try:
            bidding = result.get("bidding_strategy", {})
            phase1 = bidding.get("phase_1_bidding", {})
            
            csvc = self.client.get_service("CampaignService")
            cop = self.client.get_type("CampaignOperation")
            c = cop.create
            c.resource_name = camp_res
            
            # Start with Maximize Conversions (Phase 1)
            c.maximize_conversions.target_cpa_micros = 0
            cop.update_mask.paths.append("maximize_conversions")
            
            csvc.mutate_campaigns(
                customer_id=self.customer_id, operations=[cop]
            )
            log.info("✅ Smart bidding set: Maximize Conversions")
            return {"success": True, "strategy": "MAXIMIZE_CONVERSIONS"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def publish_ads_scripts(self, result: dict) -> dict:
        """A23 — Return scripts ready to paste in Google Ads"""
        try:
            scripts_data = result.get("ads_scripts", {})
            scripts = scripts_data.get("scripts", [])
            return {
                "success": True,
                "scripts_count": len(scripts),
                "scripts": scripts,
                "note": "Go to ads.google.com → Tools → Scripts → paste each script"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def publish_all_agents(self, result: dict, request: dict) -> dict:
        """Master publisher — runs all agents data"""
        master_result = {
            "success": False,
            "agents_published": [],
            "errors": [],
            "campaigns": {}
        }
        
        try:
            daily_budget = float(request.get("daily_budget", 50))
            
            # Create shared budget
            bsvc = self.client.get_service("CampaignBudgetService")
            bop = self.client.get_type("CampaignBudgetOperation")
            b = bop.create
            b.name = f"AdsForge Budget {int(time.time())}"
            b.amount_micros = int(daily_budget * 1_000_000)
            b.delivery_method = self.client.enums.BudgetDeliveryMethodEnum.STANDARD
            b.explicitly_shared = True
            br = bsvc.mutate_campaign_budgets(
                customer_id=self.customer_id, operations=[bop]
            )
            budget_res = br.results[0].resource_name
            master_result["campaigns"]["budget"] = budget_res

            # A17+A18+A04+A06+A08+A21+A22+A26 — Search Campaign
            search_result = self.publish(result, request)
            master_result["campaigns"]["search"] = search_result
            master_result["agents_published"].extend(
                search_result.get("published_agents", [])
            )

            # A09 — PMax Campaign
            if result.get("performance_max"):
                pmax_result = self.publish_pmax(result, request, budget_res)
                master_result["campaigns"]["pmax"] = pmax_result
                if pmax_result.get("success"):
                    master_result["agents_published"].append("A09: PMax Assets")

            # A20 — Audiences
            if result.get("audiences"):
                aud_result = self.publish_audiences(result, request)
                master_result["campaigns"]["audiences"] = aud_result
                if aud_result.get("success"):
                    master_result["agents_published"].append("A20: Audience Builder")

            # A23 — Scripts (returns ready-to-paste)
            if result.get("ads_scripts"):
                scripts_result = self.publish_ads_scripts(result)
                master_result["campaigns"]["scripts"] = scripts_result
                if scripts_result.get("success"):
                    master_result["agents_published"].append("A23: Ads Scripts")

            master_result["success"] = True
            master_result["total_agents_published"] = len(
                master_result["agents_published"]
            )
            log.info(
                f"✅ All agents published! "
                f"{master_result['total_agents_published']} agents sent to Google Ads"
            )
            return master_result

        except Exception as e:
            master_result["errors"].append(str(e))
            log.error(f"❌ Master publish failed: {e}")
            return master_result
'''

# Add methods to existing GoogleAdsPublisher class
if 'class GoogleAdsPublisher' in content:
    # Find the end of publish method and add new methods
    insert_point = content.find('    def publish(self, result: dict, request: dict) -> dict:')
    if insert_point > 0:
        # Find end of class (next non-indented line)
        class_end = content.find('\nif __name__', insert_point)
        if class_end > 0:
            content = content[:class_end] + pmax_code + content[class_end:]
            open('app_v13.py', 'w', encoding='utf-8').write(content)
            print('Done! All agent publishers added.')
        else:
            print('ERROR - could not find class end')
    else:
        print('ERROR - could not find publish method')
else:
    print('ERROR - GoogleAdsPublisher not found - run add_full_publisher.py first')