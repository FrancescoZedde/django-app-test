import pandas as pd
import re
import json
from mainapp.models import InventoryItem, Variant
from ast import literal_eval
import html
import math
from bs4 import BeautifulSoup
from mainapp.ws_cj import cj_get_shipping_methods, cj_get_inventory_inquiry




def connect_woocommerce_store(user, store_name, host, ck, cs):
    user.woocommerce_store_name = store_name
    user.woocommerce_host = host = host
    user.woocommerce_consumer_key = ck
    user.woocommerce_secret_key = cs
    user.save()

def reset_woocommerce_store(user):
    user.woocommerce_store_name = ''
    user.woocommerce_host = host = ''
    user.woocommerce_consumer_key = ''
    user.woocommerce_secret_key = ''
    user.save()

def update_woocommerce_on_sale_status(sku):
    item = InventoryItem.objects.get(sku=sku)
    if item.onsaleWoocommerce == True:
        item.onsaleWoocommerce == False
        item.save()
    else:
        item.onsaleWoocommerce == True
        item.save()

def update_ebay_on_sale_status(sku):
    item = InventoryItem.objects.get(sku=sku)
    if item.onsaleEbay == True:
        item.onsaleEbay == False
        item.save()
    else:
        item.onsaleEbay == True
        item.save()


def retrieveAllInventoryItems():
    all_inventory_items = InventoryItem.objects.all().order_by('-id')
    return all_inventory_items

def retrieveInventoryItemById(pk):
    obj = InventoryItem.objects.get(id=pk)
    return obj

def retrieveItemBySku(sku):
    item = InventoryItem.objects.get(sku=sku)
    return item

def retrieve_item_by_user_and_sku(user, sku):
    item = InventoryItem.objects.filter(user=user, sku=sku)
    return item[0]

def retrieveVariantBySku(sku):
    print(sku)
    variant = Variant.objects.get(variantSku=sku)
    return variant

def retrieveVariantsByItem(item):
    variants = Variant.objects.filter(item=item) 
    return variants

def retrieveitemByWoocommerceId(woocommerce_id):
    item = InventoryItem.objects.get(woocommerceId=woocommerce_id)
    return item

def updateWoocommerceId_sku_filter(user, sku, woocommerceId):
    item = InventoryItem.objects.filter(user=user, sku=sku)
    item[0].woocommerceId = woocommerceId
    item[0].save()
    return item[0]

def deleteItemBySku(user, sku):
    item = InventoryItem.objects.filter(user=user, sku=sku)
    try:
        item.delete()
        message = 'Item(s) deleted'
    except:
        message = 'Errore trying to delete item ' + str(sku)
    return message

def create_item_and_variants(product_details, user):
    categories_dict = parse_cj_categories(product_details)
    inventory_item = InventoryItem( user = user,
                                    sku = 'XZ' + product_details['productSku'],
                                    itemName = product_details['productNameEn'],
                                    description = product_details['description'],
                                    supplierSellPrice = product_details['sellPrice'],
                                    sellPrice = float(0.00),
                                    supplier = 'CJ',
                                    supplierSku = product_details['productSku'],
                                    categoryFirst = categories_dict['first'],
                                    categorySecond = categories_dict['second'],
                                    categoryThird = categories_dict['third'],
                                    categoryFourth = '',
                                    attributes = product_details['productKeyEn'].lower(),
                                    productWeight =  product_details['productWeight'],
                                    productType =  product_details['productType'],
                                    entryNameEn = product_details['entryNameEn'],
                                    materialNameEn = product_details['materialNameEn'],
                                    packingWeight = product_details['packingWeight'],
                                    productImage = str(literal_eval(product_details['productImage'])[0]),
                                    productImageSet =product_details['productImageSet'],
                                    jsonVariants = json.dumps(product_details['variants']),
                                    jsonDataImported = json.dumps(product_details),
                                    jsonWooCommerceExport = '',
                                    jsonWooCommerceExportVariants = '',
                                    jsonEbayExportCreateInventoryItems = '',
                                    jsonEbayExportCreateItemsGroup = '',
                                    jsonEbayExportCreateOffers = '',)
    inventory_item.save()

    
    variants = product_details['variants']
    for variant in variants:
        create_variant(inventory_item, variant)
    return inventory_item
    

def create_variant(inventory_item, variant):
    #retrive variant warehouse location
    inventory_inquiry = cj_get_inventory_inquiry(variant['vid']) 
    
    #retrieve variant shippign methods
    '''
    shipping_address_country_codes = ['US','DE','GB','IT']
    shipping_methods_list = []
    
    for end_country_code in shipping_address_country_codes:
        sm = cj_get_shipping_methods(variant['vid'], inventory_inquiry[0]['countryCode'], end_country_code)
        print(sm)
        destination_sm = {"destination": end_country_code, "shipping_method":sm}
        shipping_methods_list.append(destination_sm)'''
    variant = Variant(item = inventory_item,
                                        vid = variant['vid'],
                                        variantSku = 'XZ' + variant['variantSku'],
                                        variantNameEn = str(variant['variantNameEn']),
                                        description = 'variant description',
                                        supplierSellPrice = variant['variantSellPrice'],
                                        sellPrice = float(0.00),
                                        supplier = 'CJ',
                                        supplierSku = variant['variantSku'],
                                        variantImage= variant['variantImage'],
                                        variantKey= variant['variantKey'],
                                        variantLength= variant['variantLength'],
                                        variantWidth= variant['variantWidth'],
                                        variantHeight= variant['variantHeight'],
                                        variantVolume= variant['variantVolume'],
                                        variantWeight= variant['variantWeight'],

                                        areaId = inventory_inquiry[0]['areaId'],
                                        storageNum = inventory_inquiry[0]['storageNum'],
                                        countryCode = inventory_inquiry[0]['countryCode'],
                                        allLocations = inventory_inquiry,
                                        firstShippingMethod = '',
                                        secondShippingMethod = '',
                                        thirdShippingMethod = '',
                                        #allShippingMethods  = shipping_methods_list,
                                        )
    variant.save()

def update_items_offer(user, selected_items, percentage_increase):
    for sku in selected_items:
        print(sku)
        item_object = retrieve_item_by_user_and_sku(user, sku)
        print(item_object)
        updated_item = set_item_price(item_object, percentage_increase)        
        #updated_item.selectcategories = select_categories
        updated_item.save()

        variants_query_set = Variant.objects.filter(item=updated_item) 
        for variant in variants_query_set:
            #da aggiungere categorie + shipping options
            variant = set_variant_price(variant, percentage_increase)
            variant.save()
            

def update_item(data):
    sku = data.split("&", 1)[0]
    print(sku)
    updates_dict = string_to_dict(data)
    print(updates_dict)
    print(updates_dict)
    print('qui')
    print(BeautifulSoup(updates_dict['description'], "html.parser"))

    print(html.unescape(updates_dict['description']))

    enc = bytes(updates_dict['description'], 'utf-8')
    decodedLine = enc.decode('utf-8')

    print(decodedLine)
    item_object_set = InventoryItem.objects.filter(sku=sku)
    item_object =item_object_set[0]
    item_object.itemName = updates_dict['itemName']
    #item_object.description = decodedLine
    item_object.sellPrice = float(updates_dict['sellPrice'])
    item_object.attributes = updates_dict['attributes'].lower()

    item_object.save()

    return updates_dict

def update_variant(data):
    sku = data.split("&", 1)[0]
    print(sku)
    updates_dict = string_to_dict(data)
    variant_object_set = Variant.objects.filter(variantSku=sku)
    variant_object = variant_object_set[0]
    variant_object.variantNameEn = updates_dict['variantNameEn']
    #item_object.description = decodedLine
    variant_object.sellPrice = float(updates_dict['sellPrice'])
    variant_object.variantKey = updates_dict['variantKey'].lower()

    variant_object.save()

def string_to_dict(string):
    updates = string.split("&", 1)[1]
    updates = updates.split("&")
    updates_dict = {}
    for update in updates:
        update = update.replace('+', ' ')
        try:
            values = update.split('=',1)
            updates_dict[values[0]] = values[1]
        except:
            pass
    return updates_dict


def set_item_price(item_object, percentage_increase):
    if '-' in item_object.supplierSellPrice:

        min_and_max = item_object.supplierSellPrice.split("-")
        print(min_and_max)
        min_price = float(min_and_max[0]) + float(min_and_max[0])*float(percentage_increase)
        max_price = float(min_and_max[1]) + float(min_and_max[1])*float(percentage_increase)

        item_object.sellPrice = str(min_price) + '-' + str(max_price)

        return item_object
    else:
        supplier_price = float(item_object.supplierSellPrice)

        sell_price = supplier_price + supplier_price*float(percentage_increase)

        sell_price = math.modf(sell_price) # (0.5678000000000338, 1234.0)

        sell_price = float(sell_price[1]) + 0.99

        item_object.sellPrice = str(sell_price)

        return item_object

def set_variant_price(variant, percentage_increase):
    supplier_price = float(variant.supplierSellPrice)

    sell_price = supplier_price + supplier_price*float(percentage_increase)

    sell_price = math.modf(sell_price) # (0.5678000000000338, 1234.0)

    sell_price = float(sell_price[1]) + 0.99

    variant.sellPrice = float(sell_price)

    return variant

def parse_cj_categories(product_details):
    categories_string = product_details['categoryName']
    categories = re.split('> | /', categories_string)
    print(categories)
    categories_dict = { 'first': '',
                'second': '',
                 'third': '' }
    for i in range(len(categories)):
        if i == 0:
            categories_dict['first'] = categories[0]
        elif i == 1:
            categories_dict['second'] = categories[1]
        elif i == 2:
            categories_dict['third'] = categories[2]
    return categories_dict
