from shiny import App, render, ui, reactive
import altair as alt
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import os
import seaborn as sns
from shinywidgets import render_altair, output_widget
import sys
import json
print(sys.executable)

# Create a directory for temporary plot files if it doesn't exist
os.makedirs("temp_plots", exist_ok=True)

# Load data
geojson_path = 'data/Map_data/nyc-zips.geojson'
nyc_zips = gpd.read_file(geojson_path)
merged_df = pd.read_csv("final_education_illegal_pets.csv")

app_ui = ui.page_fluid(
    ui.h2("Illegal Pets Analysis"),
    ui.page_sidebar(
        ui.sidebar(
            ui.input_select(
                "plot_type",
                "Select Visualization",
                {
                    "choropleth": "Choropleth Map of Illegal Pets",
                    "education_trend": "Education Trends Over Time",
                    "correlation": "Education-Incidents Correlation",
                }
            ),
            # Show controls based on plot type
            ui.panel_conditional(
                "input.plot_type === 'choropleth'",
                ui.input_switch("range_toggle", "Toggle to switch to range of years"),
                ui.panel_conditional(
                    "!input.range_toggle",
                    ui.input_slider(
                        "single_year",
                        "Select Year",
                        min=2010,
                        max=2022,
                        value=2022
                    )
                ),
                ui.panel_conditional(
                    "input.range_toggle",
                    ui.input_slider(
                        "year_range",
                        "Select Year Range",
                        min=2010,
                        max=2022,
                        value=[2010, 2022]
                    )
                )
            ),
            # Add education controls
            ui.panel_conditional(
                "input.plot_type === 'education_trend'",
                ui.input_slider(
                    "edu_year_range",
                    "Select Year Range for Education Trends",
                    min=2010,
                    max=2022,
                    value=[2010, 2022]
                ),
                ui.input_checkbox_group(
                    "education_levels",
                    "Select Education Levels",
                    {
                        "pop_25_less_9th": "Less than 9th Grade",
                        "pop_25_hs_grad": "High School Graduate",
                        "pop_25_bach_plus": "Bachelor's Degree or Higher"
                    },
                    selected=["pop_25_less_9th", "pop_25_hs_grad", "pop_25_bach_plus"]
                )
            ),
            ui.panel_conditional(
                "input.plot_type === 'correlation'",
                ui.input_select(
                    "education_level",
                    "Select Education Level",
                    {
                        "pop_25_less_9th": "Less than 9th Grade",
                        "pop_25_hs_grad": "High School Graduate",
                        "pop_25_bach_plus": "Bachelor's Degree or Higher"
                    }
                ),
            )
        ),
        ui.panel_conditional(
            "input.plot_type === 'choropleth'",
            output_widget("choropleth_plot")
        ),
        ui.panel_conditional(
            "input.plot_type === 'education_trend'",
            output_widget("education_trend_plot")
        ),
        ui.panel_conditional(
            "input.plot_type === 'correlation'",
            output_widget("correlation_plot")
        )
    )
)

def server(input, output, session):
    @output
    @render_altair
    def choropleth_plot():
        if input.plot_type() != "choropleth":
            return None
        
        # Convert Created Date to datetime
        merged_df['Created Date'] = pd.to_datetime(merged_df['Created Date'])
        
        # Filter data based on toggle state
        if not input.range_toggle():
            year_data = merged_df[merged_df['Created Date'].dt.year == input.single_year()]
            title_year = str(input.single_year())
        else:
            year_range = input.year_range()
            year_data = merged_df[
                (merged_df['Created Date'].dt.year >= year_range[0]) & 
                (merged_df['Created Date'].dt.year <= year_range[1])
            ]
            title_year = f"{year_range[0]}-{year_range[1]}"
        
        # Clean and prepare data
        merged_df_clean = year_data.dropna(subset=['Incident Zip'])
        merged_df_clean['Incident Zip'] = merged_df_clean['Incident Zip'].apply(lambda x: str(int(x)))
        pet_counts = merged_df_clean.groupby('Incident Zip').size().reset_index(name='complaints_count')
        
        # Merge with GeoDataFrame and prepare for Altair
        nyc_zips_merged = nyc_zips.merge(
            pet_counts, 
            left_on='postalCode', 
            right_on='Incident Zip', 
            how='left'
        )
        nyc_zips_merged['complaints_count'] = nyc_zips_merged['complaints_count'].fillna(0)
        
        # Convert to Altair-compatible format
        zip_geojson = json.loads(nyc_zips_merged.to_json())
        zip_data = nyc_zips_merged[['postalCode', 'complaints_count']].copy()
        
        # Create Altair chart
        choropleth = alt.Chart(
            alt.Data(values=zip_geojson['features'])
        ).mark_geoshape(
            stroke='white',
            strokeWidth=0.5
        ).encode(
            color=alt.Color(
                'complaints_count:Q',
                title='Number of Complaints',
                scale=alt.Scale(scheme='orangered'),
                legend=alt.Legend(
                    orient='right',
                    title=f"Illegal Pet Complaints\n({title_year})"
                )
            ),
            tooltip=[
                alt.Tooltip('properties.postalCode:N', title='ZIP Code'),
                alt.Tooltip('properties.complaints_count:Q', title='Complaints')
            ]
        ).transform_lookup(
            lookup='properties.postalCode',
            from_=alt.LookupData(zip_data, 'postalCode', ['complaints_count'])
        ).properties(
            width=800,
            height=600,
            title=f'Illegal Pet Complaints in NYC by ZIP Code ({title_year})'
        ).configure_view(
            strokeWidth=0
        ).configure_title(
            fontSize=20,
            anchor='middle'
        )
        
        return choropleth

    @output
    @render_altair
    def education_trend_plot():
        if input.plot_type() != "education_trend":
            return None
            
        # Ensure year is numeric
        merged_df['year'] = pd.to_numeric(merged_df['year'])
        
        # Filter by selected year range
        year_range = input.edu_year_range()
        filtered_df = merged_df[
            (merged_df['year'] >= year_range[0]) & 
            (merged_df['year'] <= year_range[1])
        ]
        
        # Convert education levels tuple to list
        selected_levels = list(input.education_levels())
        
        # Prepare the data
        education_levels_over_time = filtered_df.groupby('year')[
            selected_levels
        ].mean().reset_index()

        # Convert all columns to numeric
        for col in selected_levels:
            education_levels_over_time[col] = pd.to_numeric(education_levels_over_time[col])

        education_levels_long = education_levels_over_time.melt(
            id_vars='year',
            value_vars=selected_levels,
            var_name='Education Level',
            value_name='Population'
        )

        education_level_mapping = {
            'pop_25_less_9th': 'Less than 9th Grade',
            'pop_25_hs_grad': 'High School Graduate',
            'pop_25_bach_plus': 'Bachelor\'s Degree or Higher'
        }
        education_levels_long['Education Level'] = education_levels_long['Education Level'].map(education_level_mapping)

        # Create base chart with improved styling
        chart = alt.Chart(education_levels_long).mark_line(
            point=True,
            strokeWidth=3,
            opacity=0.8
        ).encode(
            x=alt.X('year:O', 
                    title='Year',
                    axis=alt.Axis(
                        labelAngle=0,
                        labelFontSize=12,
                        titleFontSize=14
                    )),
            y=alt.Y('Population:Q', 
                    title='Average Population',
                    axis=alt.Axis(
                        labelFontSize=12,
                        titleFontSize=14,
                        format=',.0f'  # Add thousand separators
                    )),
            color=alt.Color('Education Level:N', 
                           title='Education Level',
                           legend=alt.Legend(
                               orient='right',
                               titleFontSize=12,
                               labelFontSize=11
                           )),
            tooltip=[
                alt.Tooltip('year:O', title='Year'),
                alt.Tooltip('Education Level:N', title='Education Level'),
                alt.Tooltip('Population:Q', title='Population', format=',.0f')
            ]
        ).properties(
            title={
                'text': f'Education Levels Over Time ({year_range[0]}-{year_range[1]})',
                'fontSize': 16,
                'anchor': 'middle'
            },
            width=800,
            height=500
        ).configure_view(
            strokeWidth=0
        ).configure_axis(
            grid=True,
            gridOpacity=0.2
        ).configure_point(
            size=100
        ).interactive()
    
        return chart

    @output
    @render_altair
    def correlation_plot():
        if input.plot_type() != "correlation":
            return None

        # Count illegal pet incidents by district
        incident_counts = merged_df.groupby('Borough')['Descriptor'].count().reset_index()
        incident_counts.rename(columns={'Descriptor': 'Illegal_Pet_Incidents'}, inplace=True)

        # Calculate mean education levels by district
        education_data = merged_df.groupby('Borough')[
            ['pop_25_less_9th', 'pop_25_hs_grad', 'pop_25_bach_plus', 'pop_25_plus']
        ].mean().reset_index()

        # Merge datasets
        district_data = pd.merge(incident_counts, education_data, on='Borough')

        # Calculate percentages
        district_data['Incident_Percentage(%)'] = (district_data['Illegal_Pet_Incidents'] / district_data['pop_25_plus']) * 100
        
        # Get selected education level
        feature = input.education_level()
        
        # Calculate education percentage
        district_data[f'{feature}_%'] = (district_data[feature] / district_data['pop_25_plus']) * 100
        
        # Create mapping for labels
        education_labels = {
            'pop_25_less_9th': "Population with Less than 9th Grade Education (%)",
            'pop_25_hs_grad': "Population with High School Graduation (%)",
            'pop_25_bach_plus': "Population with Bachelor's Degree or Higher (%)"
        }

        # Determine axis ranges with padding
        x_min = district_data[f'{feature}_%'].min() * 0.9
        x_max = district_data[f'{feature}_%'].max() * 1.1
        y_min = district_data['Incident_Percentage(%)'].min() * 0.9
        y_max = district_data['Incident_Percentage(%)'].max() * 1.1

        # Create scatter plot
        scatter = alt.Chart(district_data).mark_circle(
            size=100,
            opacity=0.7
        ).encode(
            x=alt.X(
                f'{feature}_%:Q',
                title=education_labels[feature],
                scale=alt.Scale(domain=[x_min, x_max])
            ),
            y=alt.Y(
                'Incident_Percentage(%):Q',
                title='Illegal Pet Incident Percentage (%)',
                scale=alt.Scale(domain=[y_min, y_max])
            ),
            tooltip=[
                alt.Tooltip('Borough:N', title='Borough'),
                alt.Tooltip(f'{feature}_%:Q', title=education_labels[feature], format='.1f'),
                alt.Tooltip('Incident_Percentage(%):Q', title='Incident %', format='.1f')
            ]
        )

        # Add text labels for boroughs
        text = scatter.mark_text(
            align='left',
            baseline='middle',
            dx=15,
            fontSize=12
        ).encode(
            text='Borough:N'
        )

        # Get the actual min and max of the x values (without padding)
        x_min_actual = district_data[f'{feature}_%'].min()
        x_max_actual = district_data[f'{feature}_%'].max()

        # Add regression line with restricted domain
        regression = scatter.transform_regression(
            f'{feature}_%', 'Incident_Percentage(%)',
            extent=[x_min_actual, x_max_actual]  # Add this line to restrict regression line
        ).mark_line(
            color='red',
            strokeWidth=2
        )

        # Combine all layers
        chart = (scatter + regression + text).properties(
            width=800,
            height=500,
            title={
                'text': f"Regression: Illegal Pet Incident Percentage vs. {education_labels[feature]}",
                'fontSize': 16,
                'anchor': 'middle'
            }
        ).configure_axis(
            labelFontSize=12,
            titleFontSize=14,
            grid=True,
            gridOpacity=0.2
        ).configure_view(
            strokeWidth=0
        )

        return chart

app = App(app_ui, server)