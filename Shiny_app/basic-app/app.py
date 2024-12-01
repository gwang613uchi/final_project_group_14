from shiny import App, render, ui, reactive
import altair as alt
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import os
import seaborn as sns

# Create a directory for temporary plot files if it doesn't exist
os.makedirs("temp_plots", exist_ok=True)

# Load data
geojson_path = 'basic-app/Map_data/nyc-zips.geojson'
nyc_zips = gpd.read_file(geojson_path)
merged_df = pd.read_csv("basic-app/final_education_illegal_pets.csv")

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
            ui.output_plot("choropleth_plot", height="600px")
        ),
        ui.panel_conditional(
            "input.plot_type === 'education_trend'",
            ui.output_plot("education_trend_plot", height="500px")
        ),
        ui.panel_conditional(
            "input.plot_type === 'correlation'",
            ui.output_plot("correlation_plot", height="500px")
        )
    )
)

def server(input, output, session):
    @output
    @render.plot
    def choropleth_plot():
        if input.plot_type() != "choropleth":
            return None
        # Convert Created Date to datetime
        merged_df['Created Date'] = pd.to_datetime(merged_df['Created Date'])
        
        # Filter data based on toggle state
        if not input.range_toggle():
            # Single year filter
            year_data = merged_df[merged_df['Created Date'].dt.year == input.single_year()]
            title_year = str(input.single_year())
        else:
            # Year range filter
            year_range = input.year_range()
            year_data = merged_df[
                (merged_df['Created Date'].dt.year >= year_range[0]) & 
                (merged_df['Created Date'].dt.year <= year_range[1])
            ]
            title_year = f"{year_range[0]}-{year_range[1]}"
        
        # Drop rows with NaN ZIP codes
        merged_df_clean = year_data.dropna(subset=['Incident Zip'])
        
        # Convert ZIP codes to strings without decimals
        merged_df_clean['Incident Zip'] = merged_df_clean['Incident Zip'].apply(lambda x: str(int(x)))
        
        # Count complaints by ZIP code
        pet_counts = merged_df_clean.groupby('Incident Zip').size().reset_index(name='complaints_count')
        
        # Merge counts with GeoDataFrame
        nyc_zips_merged = nyc_zips.merge(
            pet_counts, 
            left_on='postalCode', 
            right_on='Incident Zip', 
            how='left'
        )
        
        # Fill NaN values with 0
        nyc_zips_merged['complaints_count'] = nyc_zips_merged['complaints_count'].fillna(0)
        
        # Create the plot
        fig, ax = plt.subplots(1, 1, figsize=(15, 15))
        nyc_zips_merged.plot(
            column='complaints_count',
            ax=ax,
            legend=True,
            cmap='OrRd',
            legend_kwds={
                'label': f"Number of Illegal Pet Complaints by ZIP ({title_year})",
                'orientation': "vertical",
                'shrink': 0.8
            }
        )
        ax.set_title(f'Choropleth Map of Illegal Pet Complaints in NYC by ZIP Code ({title_year})', 
                     pad=20,
                     y=1.02
                     )
        plt.axis('off')
        plt.subplots_adjust(top=0.9)
        return fig

    @output
    @render.plot
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
        
        # Prepare the data with selected education levels
        education_levels_over_time = filtered_df.groupby('year')[
            selected_levels  # 使用转换后的列表
        ].mean().reset_index()

        # Convert all columns to numeric
        for col in selected_levels:  # 使用转换后的列表
            education_levels_over_time[col] = pd.to_numeric(education_levels_over_time[col])

        education_levels_long = education_levels_over_time.melt(
            id_vars='year',
            value_vars=selected_levels,  # 使用转换后的列表
            var_name='Education Level',
            value_name='Population'
        )

        education_level_mapping = {
            'pop_25_less_9th': 'Less than 9th Grade',
            'pop_25_hs_grad': 'High School Graduate',
            'pop_25_bach_plus': 'Bachelor\'s Degree or Higher'
        }
        education_levels_long['Education Level'] = education_levels_long['Education Level'].map(education_level_mapping)

        # Create the plot using matplotlib and seaborn
        fig, ax = plt.subplots(figsize=(12, 7))
        sns.lineplot(
            data=education_levels_long,
            x='year',
            y='Population',
            hue='Education Level',
            marker='o'
        )
        plt.title(f"Education Levels Over Time ({year_range[0]}-{year_range[1]})", fontsize=16)
        plt.xlabel("Year", fontsize=10)
        plt.ylabel("Average Population", fontsize=10)
        plt.legend(title='Education Level')
        plt.tight_layout()
        
        return fig

    @output
    @render.plot
    def correlation_plot():
        if input.plot_type() != "correlation":
            return None

        # Count illegal pet incidents by district
        incident_counts = merged_df.groupby('Borough')['Descriptor'].count().reset_index()
        incident_counts.rename(columns={'Descriptor': 'Illegal_Pet_Incidents'}, inplace=True)

        # Calculate mean education levels by district
        education_data = merged_df.groupby('Borough')[
            ['pop_25_less_9th', 'pop_25_hs_grad', 'pop_25_bach_plus', 'total_population']
        ].mean().reset_index()

        # Merge datasets
        district_data = pd.merge(incident_counts, education_data, on='Borough')

        # Calculate incident percentage
        district_data['Incident_Percentage(%)'] = (district_data['Illegal_Pet_Incidents'] / district_data['total_population']) * 100

        # Get selected education level
        feature = input.education_level()
        
        # Create mapping for labels
        education_labels = {
            'pop_25_less_9th': "Population 25+ with Less than 9th Grade Education (in 1000)",
            'pop_25_hs_grad': "Population 25+ with High School Graduation (in 1000)",
            'pop_25_bach_plus': "Population 25+ with Bachelor's Degree or Higher (in 1000)"
        }
        
        # Create the plot
        fig, ax = plt.subplots(figsize=(10, 6))
        
        # Create scatter plot with regression line
        sns.regplot(
            x=district_data[feature] / 1000,
            y=district_data['Incident_Percentage(%)'],
            ci=None,
            scatter_kws={"s": 50},
            line_kws={"color": "red"},
        )

        # Add district names to each point
        for i in range(len(district_data)):
            plt.text(
                x=district_data[feature].iloc[i] / 1000,
                y=district_data['Incident_Percentage(%)'].iloc[i],
                s=district_data['Borough'].iloc[i],
                fontsize=10,
                color="blue",
                ha="right"
            )

        # Add title and labels
        plt.title(f"Regression: Illegal Pet Incident Percentage vs. {education_labels[feature]}", 
                 fontsize=13)
        plt.xlabel(education_labels[feature], fontsize=12)
        plt.ylabel("Illegal Pet Incident Percentage(%)", fontsize=12)
        plt.tight_layout()
        
        return fig

app = App(app_ui, server)