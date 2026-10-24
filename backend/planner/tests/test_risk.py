from planner.risk import RiskLevel, WeatherObservation, apply_load_rules, assess_weather, rain_risk, snow_risk, wind_risk


def test_wind_thresholds():
    assert wind_risk(24.9) is RiskLevel.LOW
    assert wind_risk(25) is RiskLevel.MODERATE
    assert wind_risk(34.9) is RiskLevel.MODERATE
    assert wind_risk(35) is RiskLevel.HIGH
    assert wind_risk(44.9) is RiskLevel.HIGH
    assert wind_risk(45) is RiskLevel.SEVERE
    assert wind_risk(54.9) is RiskLevel.SEVERE
    assert wind_risk(55) is RiskLevel.NO_TRAVEL


def test_rain_thresholds():
    assert rain_risk(0.09) is RiskLevel.LOW
    assert rain_risk(0.10) is RiskLevel.MODERATE
    assert rain_risk(0.25) is RiskLevel.MODERATE
    assert rain_risk(0.26) is RiskLevel.HIGH
    assert rain_risk(0.50) is RiskLevel.HIGH
    assert rain_risk(0.51) is RiskLevel.SEVERE
    assert rain_risk(1.00) is RiskLevel.SEVERE
    assert rain_risk(1.01) is RiskLevel.NO_TRAVEL


def test_snow_thresholds():
    assert snow_risk(0.49) is RiskLevel.LOW
    assert snow_risk(0.5) is RiskLevel.MODERATE
    assert snow_risk(1.0) is RiskLevel.MODERATE
    assert snow_risk(1.1) is RiskLevel.HIGH
    assert snow_risk(2.0) is RiskLevel.HIGH
    assert snow_risk(2.1) is RiskLevel.SEVERE
    assert snow_risk(3.0) is RiskLevel.SEVERE
    assert snow_risk(3.1) is RiskLevel.NO_TRAVEL


def test_load_rules_upgrade_heavy_freight():
    level, note = apply_load_rules(50, 30_001, RiskLevel.SEVERE)
    assert level is RiskLevel.NO_TRAVEL
    assert note

    level, note = apply_load_rules(40, 40_001, RiskLevel.HIGH)
    assert level is RiskLevel.SEVERE
    assert note

    level, _note = apply_load_rules(40, 40_000, RiskLevel.HIGH)
    assert level is RiskLevel.HIGH

    level, _note = apply_load_rules(60, 1000, RiskLevel.LOW)
    assert level is RiskLevel.NO_TRAVEL


def test_overall_risk_uses_worst_hazard_then_load():
    light = assess_weather(WeatherObservation(wind_mph=20, rain_in_hr=0.2, snow_in_hr=0.0), load_lb=10_000)
    assert light.level is RiskLevel.MODERATE

    heavy = assess_weather(WeatherObservation(wind_mph=40, rain_in_hr=0.0, snow_in_hr=0.0), load_lb=45_000)
    assert heavy.level is RiskLevel.SEVERE
    assert any("40,000" in factor for factor in heavy.factors)
