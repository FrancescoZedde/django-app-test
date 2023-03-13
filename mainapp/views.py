from django.shortcuts import render, redirect
from ast import literal_eval
from django.http import HttpResponse
import json
import re
import pandas as pd
from urllib.parse import unquote
from django.contrib.auth.decorators import login_required
from django.contrib import messages


from mainapp.views_utils import format_results, woocommerce_extract_text_description, woocommerce_get_first_10_images, make_woocommerce_on_sale_products_list, remove_img_tags, clean_html,create_template_description_string, make_sku_list, compare_lists_and_import_missing_products, create_default_template_description_string, filter_by_keywords, create_item_and_variants_forms


from mainapp.forms import CJSearchProducts, exportSetup, InventoryItemForm, VariantForm, newStoreWoocommerce, woocommerceImportSetup, InstagramPostSetup
from mainapp.forms import EbayImportSetup, descriptionTemplate_1, descriptionTemplate_2, WritesonicDescriptionGeneratorForm, EbayUpdateAccessTokenForm
from mainapp.forms import ChatGPTWriteDescriptionForm, ChatGPTAsk
from mainapp.models import InventoryItem, Variant

from mainapp.ws_ebay_utils import ebay_create_json_inventory_item_group, ebay_create_json_inventory_item, ebay_create_json_offer
from mainapp.ws_ebay import ebay_match_product_with_ebay_catalog, ebay_search_items_by_keywords, ebay_publish_by_inventory_item_group, create_inventory_items_group, ebay_publish_offer, ebay_bulk_publish_offer, ebay_create_inventory_location, ebay_get_inventory_location, refresh_access_token, get_all_inventory_items, create_inventory_item, ebay_delete_inventory_item, bulk_create_offer

from mainapp.ws_cj import cj_products_by_category, cj_get_product_details
from mainapp.ws_woocommerce import woocommerce_retrieve_product_by_id, start_woocommerce_products_batch
from mainapp.ws_woocommerce import WooCommerce, WooCommerceConnect

from mainapp.ws_gpt import ChatGPT
from mainapp.ws_printful import Printful
from mainapp.ws_shopify import Shopify

from mainapp.ws_facebook import instagram_check_container_validity, instagram_create_container_media, instagram_create_container_carousel, instagram_publish_carousel

from mainapp.db_functions import retrieveItemBySku, reset_woocommerce_store, connect_woocommerce_store, deleteItemBySku, retrieveAllInventoryItems,update_variant, retrieveInventoryItemById, create_item_and_variants,update_items_offer,update_item



from users.models import CustomUser

#from mainapp.woocommerce_methods import woocommerce_massive_import

#from mainapp.supplier_cj import create_jsonWoocommerceExport, create_jsonWooCommerceAddVariants

@login_required(login_url='/login')
def profile(request):
    if request.method == 'GET':
        
        #class_instance = Shopify()
        #shopify_auth_url = Shopify.shopify_create_auth_url(class_instance, "sellfast-development-store")
        #Shopify.shopify_check_status()

        context = {
            #'shopify_auth_url': shopify_auth_url,
        }
        return render(request, 'mainapp/profile.html', context)

@login_required(login_url='/login')
def connect_woocommerce_store_view(request):
    if request.method == 'GET':
        return redirect(profile)
    if request.method == 'POST':
        flow = request.POST.get("woocommerce-connector",None)
        if flow == "Connect":
            try:
                print(request)
                store_name = request.POST.get("woocommerce_store_name",None)
                domain = request.POST.get("woocommerce_host",None)
                ck = request.POST.get("woocommerce_consumer_key",None)
                cs = request.POST.get("woocommerce_secret_key",None)
                connection = WooCommerceConnect(domain, ck, cs)
                if connection.status == "valid":
                    connect_woocommerce_store(request.user,store_name, domain, ck, cs)
                    messages.success(request, f"Success, WooCommerce store connected")
                else:
                    messages.error(request, f"Connection failed: invalid credentials. Retry or contact support")
                return redirect(profile)
            except:
                messages.error(request, f"Somethin goes wrong, contact Support")
                return redirect(profile)
        elif flow == "Reset":
            try:
                reset_woocommerce_store(request.user)
                messages.success(request, f"Success, you can now connect a new WooCommerce store")
                return redirect(profile)
            except:
                messages.error(request, f"Somethin goes wrong, contact Support")
                return redirect(profile)


@login_required(login_url='/login')
def trending(request):
    if request.method=='GET':
        assistant_chat_form = ChatGPTAsk()
        context = {
            'assistant_chat_form':assistant_chat_form,
        }
        return render(request, 'mainapp/trending.html', context)
    if request.method =='POST':
        question = request.POST.get('question', None)
        if question != None:
            assistant_chat_form = ChatGPTAsk()
            class_instance = ChatGPT()
            answer = ChatGPT.answer_question(class_instance, question)
            print(answer)
            context = {
                'question': question,
                'answer': answer,
                'assistant_chat_form': assistant_chat_form,
            }
            return render(request, 'mainapp/trending.html', context)



@login_required(login_url='/login')
def search(request):
    if request.method == 'GET':
        #setup = generalSetup()
        
        cj_search = CJSearchProducts()

        context = {
            'cj_search':cj_search,
        }
        return render(request, 'mainapp/search.html', context)

@login_required(login_url='/login')
def search_results(request):
    if request.method == 'GET':
        return redirect(request, 'mainapp/search.html', context)
    if request.method == 'POST':
        #setup = generalSetup()
        #simpledropdown = simpleDropdown()
        #print(request.body)
        category_id = request.POST.get('category', None)
        pagenum = request.POST.get('pagenum', None)
        pagesize = request.POST.get('pagesize', None)
        keywords = request.POST.get('keywords', None)
        if category_id != None:
            #esegui ricerca
            products = cj_products_by_category(category_id, pagenum, pagesize)
            if keywords != '':
                products = filter_by_keywords(products, keywords)
            #make a list of lists products grouped by 5
            grouped_products = format_results(products, 6)
            print('grouped')
            print(grouped_products)
            context = {
                'grouped_products':grouped_products,
                'products' : products,
            }
            return render(request, 'mainapp/search_results.html', context)
        else:
            #pagina errore
            return render(request, 'mainapp/search_results.html')




@login_required(login_url='/login')
def inventory_import(request):
    if request.method == 'GET':
        return redirect(search)
    if request.method == 'POST':
        mode = request.POST.get('import-inventory', None)
        products = InventoryItem.objects.filter(user=request.user)
        user_skus = []
        for product in products:
            user_skus.append(product.sku[2:])
        print('USER SKUS: ') 
        print(user_skus)
        if mode == 'Mass Import':
            print('start mass import')
            selected_items = request.POST.get("selected-items", None)
            selected_items = re.split(',', selected_items,)

            import_results = []
            for sku in selected_items:
                print(sku)
                print(user_skus)
                if sku in user_skus:
                    import_results.append({'sku':sku, 'code': 'error' , 'message':'SKU already in Inventory'})
                else:
                    try:
                        product_details = cj_get_product_details(sku)
                        inventory_item = create_item_and_variants(product_details, request.user)
                        import_results.append({'sku':sku, 'code': 'success' , 'message':'Success'})
                    except:
                        import_results.append({'sku':sku, 'code': 'error' , 'message':'Error'})
            context = { 'import_results' : import_results,}
            return render(request, 'mainapp/inventory_import.html', context)

        elif mode == 'Import':
            print('simple import')
            selected_item = request.POST.get("selected-item", None)
            selected_item = re.split(',', selected_item,)

            import_results = []
            for sku in selected_item:
                print(sku)
                print(user_skus)
                if sku in user_skus:
                    import_results.append({'sku':sku, 'code': 'error' , 'message':'SKU already in Inventory'})
                else:
                    try:
                        product_details = cj_get_product_details(sku)
                        inventory_item = create_item_and_variants(product_details, request.user)
                        import_results.append({'sku':sku, 'code': 'success' , 'message':'Success'})
                    except:
                        import_results.append({'sku':sku, 'code': 'error' , 'message':'Error'})

            context = { 'import_results' : import_results,}
            return render(request, 'mainapp/inventory_import.html', context)

        else:
            messages.error(request, f"Somethin goes wrong, contact Support")
            return render(request, 'mainapp/inventory_import.html')


@login_required(login_url='/login')
def inventory_list_view(request):
    if request.method == 'GET':
        all_inventory_items = retrieveAllInventoryItems()
        woocommerce_import_setup_form = woocommerceImportSetup()
        ebay_import_setup_form = EbayImportSetup()
        gpt_write_description_form = ChatGPTWriteDescriptionForm()

        products = InventoryItem.objects.filter(user=request.user)
        print('All products associated with logged user: ')
        print(products)

        context = {
            'all_inventory_items' : products,
            'woocommerce_import_setup_form': woocommerce_import_setup_form,
            'ebay_import_setup_form': ebay_import_setup_form,
            'gpt_write_description_form': gpt_write_description_form,
            'show_select_all' : 'true',

        }
        return render(request, 'mainapp/inventory_list_view.html', context)


@login_required(login_url='/login')
def inventory_list_view_manipulation_commands(request):
    if request.method == 'GET':
        return redirect(inventory_list_view)
    if request.method == 'POST':
        dropdown_value = request.POST.get("action", 'none')
        selected_items = request.POST.get("selected-items", None)
        selected_items = re.split(',', selected_items,)
        if dropdown_value == 'edit':
            print('do edit')
        elif dropdown_value == 'add-description':
            print('add-description')
            items = InventoryItem.objects.filter(user=request.user, sku__in=selected_items)
            model = request.POST.get("model", None)
            keywords = request.POST.get("keywords", '')
            min_words = request.POST.get("min_words", 80)
            max_words = request.POST.get("max_words", 200)
            rewrite_title = request.POST.get("rewrite_title", None)
            class_instance = ChatGPT()
            for item in items:
                if model == 'gpt-3.5-turbo':
                    if rewrite_title != None:
                        chatgpt_title = ChatGPT.write_product_title(class_instance, item.itemName, item.categoryThird)
                        item.itemName = chatgpt_title
                        print('GPT Completition Title:')
                        print(chatgpt_title)
                    chatgpt_description = ChatGPT.gpt35_write_product_description(class_instance, item.itemName, clean_html(item.description), keywords, max_words, min_words)
                    item.descriptionChatGpt = chatgpt_description
                    print('GPT 3.5 Description:')
                    print(chatgpt_description)
                else:
                    if rewrite_title != None:
                        chatgpt_title = ChatGPT.write_product_title(class_instance, item.itemName, item.categoryThird)
                        item.itemName = chatgpt_title
                        print('GPT Completition Title:')
                        print(chatgpt_title)
                    chatgpt_description = ChatGPT.write_product_description(class_instance, model, item.itemName, item.description, keywords)
                    item.descriptionChatGpt = chatgpt_description
                    print('GPT Completition Description:')
                    print(chatgpt_description)
                item.save()
            return redirect(inventory_list_view)
        elif dropdown_value == 'add-template':
            for item_sku in selected_items:
                item = InventoryItem.objects.filter(user=request.user, sku=item_sku)
                create_default_template_description_string(item[0])
            return redirect(inventory_list_view)

        elif dropdown_value == 'add-description-and-template':
            print('do edit')

        elif dropdown_value == 'delete':
            items = InventoryItem.objects.filter(user=request.user, sku__in=selected_items)
            for item_sku in selected_items:
                message_result = deleteItemBySku(request.user, item_sku)
            return redirect(inventory_list_view)

        elif dropdown_value == 'none':
            messages.error(request, f"Select a valid option")
            return redirect(inventory_list_view)
             
    #MASS EDIT
    #print(request.POST)
    #MASS DELETE

    #MASS ADD TEMPLATE
    return redirect(inventory_list_view)

@login_required(login_url='/login')
def inventory_list_view_import_commands(request):
    print(request.POST)
    if request.method == 'GET':
        return redirect(inventory_list_view)
    if request.method == 'POST':
        dropdown_value = request.POST.get("action", 'none')
        selected_items = request.POST.get("selected-items", None)
        selected_items = re.split(',', selected_items,)
        if dropdown_value == 'import-shopify':
            print('import to shopify')
            print(selected_items)
            items = InventoryItem.objects.filter(user=request.user, sku__in=selected_items)
            for item in items:
                variants = Variant.objects.filter(item=item) 
                #Shopify.shopify_create_new_product(item, variants)
                Shopify.shopify_create_new_product_test(item, variants)
            return redirect(inventory_list_view)
        elif dropdown_value == 'import-woocommerce':
            return redirect(inventory_list_view)
        elif dropdown_value == 'import-ebay':
            return redirect(inventory_list_view)
        elif dropdown_value == 'none':
            return redirect(inventory_list_view)

@login_required(login_url='/login')
def inventory_list_view_sync_commands(request):
    print(request.POST)
    return redirect(inventory_list_view)

@login_required(login_url='/login')
def inventory_item_detail_view(request, pk):
    #inventory-item-detail-view
    print(pk)
    gpt_write_dscription_form = ChatGPTWriteDescriptionForm()
    item = retrieveInventoryItemById(pk)
    item_original_description = remove_img_tags(item.description)
    img_set = literal_eval(item.productImageSet)
    item_form = InventoryItemForm(instance=item)
    context = {'pk': pk, 
                'item':item,
                'item_form': item_form,
                'item_original_description':item_original_description,
                'img_set':img_set,
                'gpt_write_dscription_form': gpt_write_dscription_form,
                }
    return render(request, 'mainapp/inventory_item_detail_view.html', context)

@login_required(login_url='/login')
def inventory_item_detail_view_save_changes(request):
    primary_key = request.POST.get("primary-key", None)
    new_name = request.POST.get("itemName", None)
    new_description = request.POST.get("description", None)
    new_brand = request.POST.get("brand", None)
    new_descriptionFeatures = request.POST.get("descriptionFeatures", '')

    item = retrieveInventoryItemById(primary_key)
    item.itemName = new_name
    item.description = new_description
    item.descriptionFeatures = new_descriptionFeatures
    item.brand = new_brand
    item.save()

    return redirect(inventory_item_detail_view, pk=primary_key)

@login_required(login_url='/login')
def inventory_item_detail_view_save_main_AI_manual_changes(request):
    primary_key = request.POST.get("primary-key", None)
    new_descriptionChatGpt = request.POST.get("descriptionChatGpt", None)

    item = retrieveInventoryItemById(primary_key)
    item.descriptionChatGpt = new_descriptionChatGpt
    
    item.save()

    return redirect(inventory_item_detail_view, pk=primary_key)

@login_required(login_url='/login')
def inventory_item_remove_image(request):
    img_url = request.POST.get("img-url", None)
    primary_key = request.POST.get("primary-key", None)
    item = retrieveInventoryItemById(primary_key)
    img_set = literal_eval(item.productImageSet)
    img_set.remove(img_url)
    item.productImageSet = str(img_set)
    item.save()
    return redirect(inventory_item_detail_view, pk=primary_key)

@login_required(login_url='/login')
def inventory_item_set_main_image(request):
    img_url = request.POST.get("img-url", None)
    primary_key = request.POST.get("primary-key", None)
    item = retrieveInventoryItemById(primary_key)
    # set as main
    item.productImage = img_url

    # remove and re-add as first element in img set
    img_set = literal_eval(item.productImageSet)
    img_set.remove(img_url)
    img_set.insert(0, img_url)
    item.productImageSet = str(img_set)

    #save
    item.save()

    return redirect(inventory_item_detail_view, pk=primary_key)

@login_required(login_url='/login')
def inventory_item_search_similar_items(request):
    if request.method == 'POST':
        primary_key = request.POST.get("primary-key", None)
        keywords = request.POST.get("item-name", None)
        user_instance = CustomUser.objects.get(email=request.user.email)
        if keywords != None:
            response = ebay_search_items_by_keywords(user_instance.ebay_access_token, keywords)
            if type(response) == list:
                #visualizza gli items
                context = {
                    'items': response,
                    'primary_key' : primary_key,
                    }
                return render(request, 'mainapp/inventory_item_search_similar_items.html', context)
            else:
                messages.error(request, f"Somethin goes wrong, Ebay returns {response}")
                return redirect(inventory_item_detail_view, pk=primary_key)
        else:
            messages.error(request, f"Somethin goes wrong")
            return redirect(inventory_item_detail_view, pk=primary_key)




@login_required(login_url='/login')
def inventory_sync(request):
    if request.method == 'GET':
        return redirect(inventory_list_view)
    if request.method == 'POST':
        #retireve app inventory items
        all_inventory_items = retrieveAllInventoryItems()
        #make list
        inventory_sku_list = make_sku_list(all_inventory_items, 'app-inventory')

        if 'sync-with-woocommerce' in request.POST:
            print('START sync-with-woocommerce')
            class_instance = WooCommerce()
            woocommerce_items = WooCommerce.woocommerce_retrieve_all_products(class_instance)
            woocommerce_sku_list = make_sku_list(woocommerce_items, 'sync-woocommerce')
            results = compare_lists_and_import_missing_products(inventory_sku_list, woocommerce_sku_list)

        elif 'sync-with-ebay' in request.POST:
            print('START sync-with-ebay')
            '''
            #retrieve ebay items
            ebay_items = ebay_retrieve_all_products()
            #make list
            ebay_sku_list = make_sku_list(ebay_items, 'sync-ebay')
            #compare con inventory_sku_list
            results = compare_lists(inventory_sku_list, ebay_sku_list)'''

        context = {
            'all_inventory_items' : all_inventory_items,
        }

        return redirect(inventory_list_view)

@login_required(login_url='/login')
def inventory_edit_items(request):
    #data = request.GET.get("company_id", None)
    #print(data)
    if request.method == 'POST':
        export_setup_form = exportSetup()
        woocommerce_categories = get_woocommerce_categories()
        selected_items = request.POST.get("selected-items", None)
        selected_items = re.split(',', selected_items,)

        #get items
        items = InventoryItem.objects.filter(sku__in=selected_items)
        
        item_and_variants_list = []
        for item in items:
            #get item variants
            variants = Variant.objects.filter(item=item)
            #create item and variants forms
            form_dict = create_item_and_variants_forms(item, variants)

            item_and_variants_list.append(form_dict)
        #append to
        form = InventoryItemForm(instance=item)
        forms_list = []
        forms_list.append(form)
        context = {
            'selected_items':selected_items,
            'export_setup_form':export_setup_form,
            'form':form,
            'forms_list':forms_list,
            'item_and_variants_list': item_and_variants_list,
            'woocommerce_categories':woocommerce_categories
        }
        return render(request, 'mainapp/inventory_edit_items.html',context)
    if request.method == 'GET':
        return redirect(inventory_list_view)

@login_required(login_url='/login')
def export_start(request):
    if request.method == 'GET':
        return redirect(inventory_list_view)
    if request.method == 'POST':
        selected_items = request.POST.get("selected-items", None)
        percentage_increase = request.POST.get("pricepercentageincrease", None)
        categories = request.POST.get("categories", None)
        #select_categories = request.POST.get("selectcategories", None)

        selected_items = re.split(',', selected_items,)
        categories = re.split(',', categories,)

        update_items_offer(request.user, selected_items, percentage_increase)
        #start_woocommerce_products_batch(selected_items, categories)
        class_instance = WooCommerce(request.user)
        WooCommerce.start_woocommerce_products_batch(class_instance, selected_items, categories )
    
        context = {
            'all_inventory_items':'ok',
        }

        messages.success(request, f"Products are online on your shop!")
        return redirect(inventory_list_view)
    else:
        messages.success(request, f"Something goes wrong :/")
        return redirect(inventory_list_view)



@login_required(login_url='/login')
def ebay_connect_store(request):
    if request.method == 'GET':
        ebay_update_access_token_form = EbayUpdateAccessTokenForm()
        ebay_access_token = request.user.ebay_access_token
        context = {
            'ebay_update_access_token_form' : ebay_update_access_token_form,
            'ebay_access_token' : ebay_access_token,
        }
        return render(request, 'mainapp/ebay_connect_store.html', context)

@login_required(login_url='/login')
def ebay_update_access_token(request):
    if request.method == 'GET':
        return redirect(ebay_connect_store)
    elif request.method == 'POST':
        new_access_token = request.POST.get("access_token", '')
        user_instance = CustomUser.objects.get(email=request.user.email)

        user_instance.ebay_access_token = new_access_token
        user_instance.save()
        return redirect(ebay_connect_store)


@login_required(login_url='/login')
def ebay_start_export_batch(request):
    if request.method == 'POST':
        selected_items = request.POST.get("selected-items-ebay", None)
        price_multiplier = request.POST.get("price_multiplier", 2)
        print('PRICE MULTIPLER:' + str(price_multiplier))
        selected_items = re.split(',', selected_items,)
        user_instance = CustomUser.objects.get(email=request.user.email)
        print(selected_items)
        for item_sku in selected_items:
            print(item_sku)

            #ebay_match_product_with_ebay_catalog(user_instance.ebay_access_token, 'Ku102 Mechanical Keyboard Wireless Bluetooth Office Tea Shaft', '')
            
            payload = ebay_create_json_inventory_item(item_sku)

            create_response = create_inventory_item(user_instance.ebay_access_token, payload)

            inventory_item_group_key, payload_inventory_item_group = ebay_create_json_inventory_item_group(item_sku)

            create_inventory_items_group(user_instance.ebay_access_token, payload_inventory_item_group, inventory_item_group_key)


            payload_offers = ebay_create_json_offer(item_sku, price_multiplier)


            responses = bulk_create_offer(user_instance.ebay_access_token, payload_offers)

            publish_inventory_item_response = ebay_publish_by_inventory_item_group(user_instance.ebay_access_token, inventory_item_group_key)

            try:
                if publish_inventory_item_response['errors'][0]['errorId'] == 25001:
                    print('PUBLISH BY INVENTORY ITEM GROUP DIDNT WORK')
                    for response in responses:
                        ebay_publish_offer(user_instance.ebay_access_token, response['offerId'])
            except:
                pass

        return redirect(ebay_inventory)


@login_required(login_url='/login')
def ebay_inventory(request):
    if request.method == 'GET':
        user_instance = CustomUser.objects.get(email=request.user.email)
        inventory_items = get_all_inventory_items(user_instance.ebay_access_token)
        context = {
            'inventory_items':inventory_items['inventoryItems'],
            }
        return render(request, 'mainapp/ebay_inventory.html', context)


@login_required(login_url='/login')
def ebay_delete_inventory_items(request):
    if request.method == 'POST':
        selected_items = request.POST.get("selected-items", None)

        selected_items = re.split(',', selected_items,)

        user_instance = CustomUser.objects.get(email=request.user.email)
        #delete by sku
        for item_sku in selected_items:
            print(item_sku)
            ebay_delete_inventory_item(item_sku, user_instance.ebay_access_token)
            #print(result)

        return redirect(ebay_inventory)


@login_required(login_url='/login')
def gpt_generate_description(request):
    if request.method == 'POST': 

        primary_key = request.POST.get("primary-key", None)
        items = InventoryItem.objects.filter(user=request.user, id=primary_key)
        model = request.POST.get("model", None)
        keywords = request.POST.get("keywords", '')
        min_words = request.POST.get("min_words", 80)
        max_words = request.POST.get("max_words", 200)
        rewrite_title = request.POST.get("rewrite_title", None)
        class_instance = ChatGPT()
        for item in items:
            if model == 'gpt-3.5-turbo':
                if rewrite_title != None:
                    chatgpt_title = ChatGPT.write_product_title(class_instance, item.itemName, item.categoryThird)
                    item.itemName = chatgpt_title
                    print('GPT Completition Title:')
                    print(chatgpt_title)
                chatgpt_description = ChatGPT.gpt35_write_product_description(class_instance, item.itemName, clean_html(item.description), keywords, max_words, min_words)
                item.descriptionChatGpt = chatgpt_description
                print('GPT 3.5 Description:')
                print(chatgpt_description)
            else:
                if rewrite_title != None:
                    chatgpt_title = ChatGPT.write_product_title(class_instance, item.itemName, item.categoryThird)
                    item.itemName = chatgpt_title
                    print('GPT Completition Title:')
                    print(chatgpt_title)
                chatgpt_description = ChatGPT.write_product_description(class_instance, model, item.itemName, item.description, keywords)
                item.descriptionChatGpt = chatgpt_description
                print('GPT Completition Description:')
                print(chatgpt_description)
            item.save()

        return redirect(inventory_item_detail_view, pk=primary_key)



@login_required(login_url='/login')
def woocommerce_categories(request):
    if request.method == "GET":
        class_instance = WooCommerce(request.user)
        woocommerce_categories = WooCommerce.get_woocommerce_categories(class_instance)
        context = {
            'woocommerce_categories':woocommerce_categories
            }
        return render(request, 'mainapp/woocommerce_categories.html', context)

@login_required(login_url='/login')
def woocommerce_onsale(request):
    if request.method == "GET":
        class_instance = WooCommerce(request.user)
        woocommerce_products = WooCommerce.woocommerce_retrieve_all_products(class_instance)
        ig_post_setup_form = InstagramPostSetup()
        products = make_woocommerce_on_sale_products_list(woocommerce_products)

        context = {'products': products,
                    'ig_post_setup_form':ig_post_setup_form,
                    }
        return render(request, 'mainapp/woocommerce_onsale.html', context)

# SOCIAL NETWORK
@login_required(login_url='/login')
def social_settings(request):
    if request.method == 'GET':
        return render(request, 'mainapp/social_settings.html')


@login_required(login_url='/login')
def social_instagram(request):
    if request.method == 'GET':
        return render(request, 'mainapp/social_instagram.html')

@login_required(login_url='/login')
def social_facebook(request):
    if request.method == 'GET':
        return render(request, 'mainapp/social_facebook.html')

@login_required(login_url='/login')
def facebook_login(request):
    if request.method == 'GET':
        return render(request, 'mainapp/facebook_login.html')

@login_required(login_url='/login')
def facebook_update_connection(request):
    if request.method == 'POST':
        try:
            new_token = request.POST.get("new-access-token", None)
            fb_user_id = request.POST.get("fb-user-id", None)
            fb_page_id = request.POST.get("fb-page-id", None)
            ig_user_id = request.POST.get("ig-user-id", None)
            print('here')
            user_instance = CustomUser.objects.get(email=request.user.email)
            user_instance.facebook_access_token = new_token
            user_instance.facebook_user_id = fb_user_id
            user_instance.facebook_page_id = fb_page_id
            user_instance.instagram_user_id = ig_user_id
            print('here1')
            user_instance.save()
            print('here2')
            messages.success(request, f"Access token updated")
            return redirect(facebook_login)
        except:
            messages.error(request, f"Somethin goes wrong")
            return redirect(facebook_login)
    elif request.method == 'GET':
        return redirect(facebook_login)


@login_required(login_url='/login')
def instagram_create_post(request):
    if request.method == 'POST':
        user_instance = CustomUser.objects.get(email=request.user.email)
        woocommerce_id = request.POST.get("ig-selected-item", None)
        is_carousel = request.POST.get("is_carousel", None)
        caption = request.POST.get("caption", None)
        use_woocommerce_description = request.POST.get("use_woocommerce_description", None)
        print(use_woocommerce_description)
        print(woocommerce_id)
        print(is_carousel)
        print(caption)
        woocommerce_product = woocommerce_retrieve_product_by_id(woocommerce_id)
        if is_carousel != None:
            print("make carousel")
            image_urls = woocommerce_get_first_10_images(woocommerce_product)
            print(image_urls)
            ids_list = []
            ids_array = ''
            for url in image_urls:
                id_media_container = instagram_create_container_media(user_instance, url, caption, True)                
                ids_array = ids_array + id_media_container + '%2C'
                ids_list.append(id_media_container)

            for id_container in ids_list:
                instagram_check_container_validity(user_instance, id_container)
            ids_array = ids_array[:-3]
            print(ids_array)

            if use_woocommerce_description != None:
                item = retrieveItemBySku(woocommerce_product['sku'])
                print('NEW CAPTION')
                print(item.descriptionChatGpt)
                caption = item.descriptionChatGpt
            carousel_id = instagram_create_container_carousel(user_instance, ids_array, caption)
            # pubblica container carosello
            instagram_publish_carousel(user_instance, carousel_id)

        else:
            #make single media post
            print("make single media post")
            #instagram_create_container_media(user, url_image, caption, False)
        
        #instagram_create_container_media(user_instance,'https://xzshop.eu/wp-content/uploads/2023/02/61147517-3ead-4574-a7d0-bad816dba54b-1.jpg')
        return redirect(social_instagram)


def printful_oauth(request):
    # get access token
    printful = Printful()
    Printful.get_scopes(printful)
    #access_token, refresh_token = Printful.get_access_token(printful)
    #Printful.refresh_token(printful, refresh_token)
    return redirect(profile)