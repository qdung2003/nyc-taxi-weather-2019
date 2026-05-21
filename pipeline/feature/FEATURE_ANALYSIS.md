# Taxi Weather Feature Analysis

## Objective

Analyze the relationship between daily weather features and taxi trip metrics after joining taxi and weather data by date.

Weather features:

- `prcp`: precipitation
- `avg_temp`: average temperature
- `temp_range`: daily temperature range

Taxi metrics:

- `avg_trip_count`
- `avg_duration_minutes`
- `avg_trip_distance`
- `avg_fare_amount`
- `avg_tip_amount`
- `avg_total_amount`

## Main Findings

`avg_temp` shows the clearest relationship with taxi behavior. Taxi metrics fluctuate more across average temperature levels than across precipitation or temperature range levels. The pattern is not strictly linear: metrics do not simply increase or decrease as temperature rises. Instead, they vary around more comfortable temperature ranges.

`prcp` has a weaker effect. Rain appears to be associated with small changes in taxi activity, especially `avg_trip_count` and `avg_trip_distance`, but the magnitude is generally limited.

`temp_range` does not show a clear effect. Most taxi metrics change only slightly across daily temperature range levels, so it is not a strong explanatory weather feature in this EDA.

`avg_fare_amount` also does not show a clear direct weather effect. Fare changes are likely influenced more by trip distance, duration, and other demand patterns than by weather alone.

## Summary

Among the weather features, `avg_temp` has the strongest signal, `prcp` has a smaller signal, and `temp_range` is weak. The analysis suggests weather is related to taxi behavior, but the current EDA is not enough to claim direct causality.

## Limitations

- Weather data is daily, not hourly.
- Joining by date can hide short-term weather effects during specific hours.
- Other factors such as weekday/weekend, season, holidays, demand, and traffic are not fully controlled.
- The results should be interpreted as EDA signals, not causal proof.
